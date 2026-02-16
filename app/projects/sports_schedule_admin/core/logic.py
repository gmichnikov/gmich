import logging
import time
from datetime import datetime, timedelta
from app.projects.sports_schedule_admin.core.espn_client import ESPNClient
from app.projects.sports_schedule_admin.core.dolthub_client import DoltHubClient
from app.models import LogEntry, db

logger = logging.getLogger(__name__)

def sync_league_range(league_code, start_date, end_date, actor_id=None):
    """
    Sync a range of dates for a given league.
    """
    espn = ESPNClient()
    dolt = DoltHubClient()
    
    current_date = start_date
    total_games_found = 0
    total_upserted = 0
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")
        logger.info(f"Syncing {league_code} for {date_str}...")
        
        games = espn.fetch_schedule(league_code, date_str)
        if games:
            total_games_found += len(games)
            # Batch upsert to DoltHub
            # The dolt_client uses INSERT ... ON DUPLICATE KEY UPDATE
            # which prevents duplicate primary_key entries.
            result = dolt.batch_upsert("combined-schedule", games)
            
            if result and "error" not in result:
                total_upserted += len(games)
            else:
                logger.error(f"Failed to upsert games for {date_str}: {result.get('error')}")
        
        current_date += timedelta(days=1)
        # Polite delay to avoid rate limits
        # Note: DoltHub write operations also add natural delay due to polling
        time.sleep(1.0) 
    
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
