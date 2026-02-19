import logging
import time
from datetime import datetime, timedelta
from app.projects.sports_schedule_admin.core.espn_client import ESPNClient
from app.projects.sports_schedule_admin.core.mlb_client import MLBClient
from app.projects.sports_schedule_admin.core.leagues import ALL_LEAGUE_CODES, is_milb_league
from app.core.dolthub_client import DoltHubClient
from app.models import LogEntry, db, ESPNCollegeTeam

logger = logging.getLogger(__name__)


def sync_league_teams(league_code, actor_id=None):
    """
    Fetch and sync the team registry for a college league from ESPN.
    """
    if league_code not in ALL_LEAGUE_CODES:
        raise ValueError(f"Unsupported league: {league_code}")

    espn = ESPNClient()
    teams = espn.fetch_teams(league_code)
    
    if not teams:
        return {"league": league_code, "created": 0, "updated": 0}

    created = 0
    updated = 0
    
    for t_data in teams:
        # Check if team exists for this league
        team = ESPNCollegeTeam.query.filter_by(
            espn_team_id=t_data["espn_team_id"],
            league_code=league_code
        ).first()
        
        if team:
            # Update existing
            team.name = t_data["name"]
            team.abbreviation = t_data["abbreviation"]
            team.sport = t_data["sport"]
            updated += 1
        else:
            # Create new
            team = ESPNCollegeTeam(
                espn_team_id=t_data["espn_team_id"],
                name=t_data["name"],
                abbreviation=t_data["abbreviation"],
                sport=t_data["sport"],
                league_code=league_code
            )
            db.session.add(team)
            created += 1
            
    db.session.commit()
    
    # Log the activity
    try:
        log_desc = f"Discovered teams for {league_code}. Found {len(teams)} teams (Created {created}, Updated {updated})."
        log_entry = LogEntry(
            project="sports_admin",
            category="Discovery",
            actor_id=actor_id,
            description=log_desc
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log discovery activity: {e}")

    return {
        "league": league_code,
        "found": len(teams),
        "created": created,
        "updated": updated
    }


def sync_league_range(league_code, start_date, end_date, actor_id=None):
    """
    Sync a range of dates for a given league.
    Uses ESPN for major leagues, MLB Stats API for MiLB (AAA, AA, A+, A).
    """
    if league_code not in ALL_LEAGUE_CODES:
        raise ValueError(f"Unsupported league: {league_code}")

    dolt = DoltHubClient()
    total_games_found = 0
    total_upserted = 0

    if is_milb_league(league_code):
        # MiLB: one API call per league for full date range (chunked if >90 days)
        mlb = MLBClient()
        logger.info(f"Syncing {league_code} from {start_date} to {end_date}...")
        games = mlb.fetch_schedule(league_code, start_date, end_date)
        total_games_found = len(games)
        if games:
            result = dolt.batch_upsert("combined-schedule", games)
            if result:
                total_upserted = result.get("upserted", 0)
                if "error" in result:
                    logger.error(f"Partial upsert: {result.get('error')} ({total_upserted}/{len(games)} succeeded)")
    else:
        # ESPN: day-by-day
        espn = ESPNClient()
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y%m%d")
            logger.info(f"Syncing {league_code} for {date_str}...")

            games = espn.fetch_schedule(league_code, date_str)
            if games:
                total_games_found += len(games)
                result = dolt.batch_upsert("combined-schedule", games)
                if result:
                    upserted = result.get("upserted", 0)
                    total_upserted += upserted
                    if "error" in result:
                        logger.error(f"Partial upsert for {date_str}: {result.get('error')} ({upserted}/{len(games)} succeeded)")

            current_date += timedelta(days=1)
            time.sleep(1.0)  # Polite delay for ESPN rate limits
    
    # Log the activity
    try:
        log_desc = f"Synced {league_code} from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}. Found {total_games_found}, Upserted {total_upserted}."
        log_entry = LogEntry(
            project="sports_admin",
            category="Sync",
            actor_id=actor_id,
            description=log_desc
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log sync activity: {e}")

    return {
        "league": league_code,
        "games_found": total_games_found,
        "upserted": total_upserted
    }

def sync_team_schedule(league_code, team_id, actor_id=None):
    """
    Fetch and sync the full season schedule for a specific team.
    """
    if league_code not in ALL_LEAGUE_CODES:
        raise ValueError(f"Unsupported league: {league_code}")

    espn = ESPNClient()
    games = espn.fetch_team_schedule(league_code, team_id)
    
    if not games:
        return {"league": league_code, "team_id": team_id, "upserted": 0, "games_found": 0}

    dolt = DoltHubClient()
    result = dolt.batch_upsert("combined-schedule", games)
    upserted = result.get("upserted", 0) if result else 0

    # Update team sync timestamp
    team = ESPNCollegeTeam.query.filter_by(espn_team_id=team_id, league_code=league_code).first()
    if team:
        team.last_synced_at = datetime.utcnow()
        db.session.commit()
    
    # Log the activity
    try:
        team_name = team.name if team else team_id
        log_desc = f"Synced full schedule for {team_name} ({league_code}). Found {len(games)} games, Upserted {upserted}."
        log_entry = LogEntry(
            project="sports_admin",
            category="Team Sync",
            actor_id=actor_id,
            description=log_desc
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log team sync activity: {e}")

    return {
        "league": league_code,
        "team_id": team_id,
        "games_found": len(games),
        "upserted": upserted
    }

def clear_league_data(league_code, start_date=None, end_date=None, actor_id=None):
    """
    Delete games for a specific league from DoltHub.
    - No dates: delete all
    - Start only: delete from start onward
    - Start + end: delete that date range (inclusive)
    """
    dolt = DoltHubClient()
    sql = f"DELETE FROM `combined-schedule` WHERE `league` = '{league_code}'"

    if start_date:
        date_str = start_date.strftime("%Y-%m-%d")
        sql += f" AND `date` >= '{date_str}'"
    if end_date:
        date_str = end_date.strftime("%Y-%m-%d")
        sql += f" AND `date` <= '{date_str}'"

    result = dolt.execute_sql(sql)

    if result and "error" not in result:
        try:
            if start_date and end_date:
                date_info = f" from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            elif start_date:
                date_info = f" from {start_date.strftime('%Y-%m-%d')}"
            else:
                date_info = ""
            log_entry = LogEntry(
                project="sports_admin",
                category="Clear Data",
                actor_id=actor_id,
                description=f"Cleared {league_code} data{date_info}."
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to log clear activity: {e}")

    return result
