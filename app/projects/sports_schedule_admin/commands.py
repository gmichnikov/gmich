import click
from datetime import datetime, timedelta
from app.projects.sports_schedule_admin.core.logic import sync_league_range, sync_league_teams
from app.projects.sports_schedule_admin.core.espn_client import (
    STATE_NAME_TO_CODE,
    US_STATE_CODES,
)

def init_app(app):
    """Register CLI commands with the Flask app"""

    @app.cli.group("sports-admin")
    def sports_admin():
        """Sports Schedule Admin commands"""
        pass

    @sports_admin.command("sync-teams")
    @click.option("--league", required=True, help="League code for team discovery (e.g., NCAAM, NCB, NCHM, NCSM)")
    def sync_teams(league):
        """Discover and sync the team registry for a college league from ESPN"""
        try:
            click.echo(f"Discovering teams for {league}...")
            result = sync_league_teams(league)
            click.echo(f"Discovery complete for {result['league']}:")
            click.echo(f"  - Teams found: {result['found']}")
            click.echo(f"  - Teams created: {result['created']}")
            click.echo(f"  - Teams updated: {result['updated']}")
        except Exception as e:
            click.echo(f"An error occurred: {e}", err=True)

    @sports_admin.command("sync-team")
    @click.option("--league", required=True, help="League code (e.g., NCAAM, NCB)")
    @click.option("--team-id", required=True, help="ESPN Team ID")
    def sync_team(league, team_id):
        """Sync full season schedule for a specific team"""
        from app.projects.sports_schedule_admin.core.logic import sync_team_schedule
        try:
            click.echo(f"Starting season sync for {league} team {team_id}...")
            result = sync_team_schedule(league, team_id)
            click.echo(f"Sync complete:")
            click.echo(f"  - Games found: {result['games_found']}")
            click.echo(f"  - Games upserted: {result['upserted']}")
        except Exception as e:
            click.echo(f"An error occurred: {e}", err=True)

    @sports_admin.command("sync-bulk")
    @click.option("--league", required=True, help="League code (e.g., NCAAM, NCB)")
    @click.option("--team-ids", help="Comma-separated ESPN Team IDs (omit to sync all discovered teams)")
    def sync_bulk(league, team_ids):
        """Sync full season schedules for multiple teams. Omit --team-ids to sync all."""
        from app.projects.sports_schedule_admin.core.logic import sync_bulk_teams
        from app.models import ESPNCollegeTeam
        try:
            if team_ids:
                ids = [t.strip() for t in team_ids.split(",") if t.strip()]
            else:
                teams = ESPNCollegeTeam.query.filter_by(league_code=league).all()
                ids = [t.espn_team_id for t in teams]
            if not ids:
                click.echo("No teams to sync. Run sync-teams first to discover teams.", err=True)
                return
            click.echo(f"Starting bulk sync for {league} ({len(ids)} teams)...")
            result = sync_bulk_teams(league, ids)
            click.echo(f"Bulk sync complete:")
            click.echo(f"  - Teams synced: {result['teams_synced']}")
            click.echo(f"  - Games found: {result['games_found']}")
            click.echo(f"  - Games upserted: {result['upserted']}")
        except Exception as e:
            click.echo(f"An error occurred: {e}", err=True)

    @sports_admin.command("sync")
    @click.option("--league", required=True, help="League code (MLB, NCB, NBA, NFL, NHL, MLS, NWSL, NCSM, NCSW, EPL, AAA, AA, A+, A)")
    @click.option("--start", help="Start date (YYYY-MM-DD), defaults to today")
    @click.option("--end", help="End date (YYYY-MM-DD), defaults to today")
    @click.option("--days", type=int, help="Number of days to sync from start date")
    def sync(league, start, end, days):
        """Sync sports data for a specific league and date range"""
        try:
            if start:
                start_dt = datetime.strptime(start, "%Y-%m-%d")
            else:
                start_dt = datetime.now()

            if end:
                end_dt = datetime.strptime(end, "%Y-%m-%d")
            elif days:
                end_dt = start_dt + timedelta(days=days - 1)  # inclusive: 7 days = start through start+6
            else:
                end_dt = start_dt

            click.echo(f"Starting sync for {league} from {start_dt.date()} to {end_dt.date()}...")
            
            result = sync_league_range(league, start_dt, end_dt)
            
            click.echo(f"Sync complete for {result['league']}:")
            click.echo(f"  - Games found: {result['games_found']}")
            click.echo(f"  - Games upserted: {result['upserted']}")
            
        except ValueError as e:
            click.echo(f"Error: Invalid date format. Use YYYY-MM-DD. ({e})", err=True)
        except Exception as e:
            click.echo(f"An error occurred: {e}", err=True)

    @sports_admin.command("daily-sync")
    def daily_sync():
        """Daily sync for all major leagues (Next 7 days)"""
        leagues = ["MLB", "NBA", "NFL", "NHL", "MLS", "NWSL", "EPL"]
        start_dt = datetime.now()
        end_dt = start_dt + timedelta(days=7)
        
        click.echo(f"Starting daily sync for all leagues from {start_dt.date()} to {end_dt.date()}...")
        
        for league in leagues:
            click.echo(f"Syncing {league}...")
            result = sync_league_range(league, start_dt, end_dt)
            click.echo(f"  {league}: {result['upserted']} games updated.")
        
        click.echo("Daily sync complete.")

    @sports_admin.command("check-coverage")
    @click.option("--league", required=True, help="League code (e.g. AA, AAA)")
    @click.option("--start", required=True, help="Start date (YYYY-MM-DD)")
    @click.option("--end", required=True, help="End date (YYYY-MM-DD)")
    def check_coverage(league, start, end):
        """Query DoltHub for game counts per date. Use to verify sync results."""
        from app.core.dolthub_client import DoltHubClient

        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            end_dt = datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            click.echo("Error: Invalid date format. Use YYYY-MM-DD.", err=True)
            return

        dolt = DoltHubClient()
        sql = f"""
            SELECT `date`, COUNT(*) AS games
            FROM `combined-schedule`
            WHERE `league` = '{league}'
              AND `date` >= '{start_dt.date()}'
              AND `date` <= '{end_dt.date()}'
            GROUP BY `date`
            ORDER BY `date`
        """
        result = dolt.execute_sql(sql)
        if result and "error" in result:
            click.echo(f"Error: {result['error']}", err=True)
            return

        rows = result.get("rows", [])
        if not rows:
            click.echo(f"No {league} games in DoltHub for {start} to {end}.")
            return

        click.echo(f"{league} coverage {start} to {end}:")
        for r in rows:
            click.echo(f"  {r.get('date')}: {r.get('games', 0)} games")
        total = sum(int(r.get("games", 0)) for r in rows)
        click.echo(f"  TOTAL: {total} games across {len(rows)} dates")

    @sports_admin.command("clear-league")
    @click.option("--league", required=True, help="League code to clear (e.g. MLB, AAA)")
    @click.option("--start", help="Only clear games on or after this date (YYYY-MM-DD)")
    @click.option("--end", help="Only clear games on or before this date (YYYY-MM-DD)")
    @click.option("--days", type=int, help="Number of days from start date (use with --start)")
    def clear_league(league, start, end, days):
        """Delete games for a specific league from DoltHub"""
        from app.projects.sports_schedule_admin.core.logic import clear_league_data

        start_dt = None
        end_dt = None
        if start:
            try:
                start_dt = datetime.strptime(start, "%Y-%m-%d")
            except ValueError:
                click.echo("Error: Invalid date format. Use YYYY-MM-DD.", err=True)
                return
        if end:
            try:
                end_dt = datetime.strptime(end, "%Y-%m-%d")
            except ValueError:
                click.echo("Error: Invalid date format. Use YYYY-MM-DD.", err=True)
                return
        elif days and start_dt:
            end_dt = start_dt + timedelta(days=days - 1)

        range_desc = "all data" if not start_dt else f"from {start_dt.date()}" + (f" to {end_dt.date()}" if end_dt else " onward")
        click.confirm(f"This will delete {league} {range_desc} from DoltHub. Continue?", abort=True)

        click.echo(f"Clearing {league} data...")
        result = clear_league_data(league, start_dt, end_dt)

        if result and "error" not in result:
            click.echo("Data cleared successfully.")
        else:
            click.echo(f"Error: {result.get('error')}", err=True)

    @sports_admin.command("normalize-states")
    @click.option("--dry-run", is_flag=True, help="Show what would be updated without making changes")
    def normalize_states(dry_run):
        """Convert full state names to 2-letter codes in combined-schedule home_state column"""
        from app.core.dolthub_client import DoltHubClient

        dolt = DoltHubClient()
        result = dolt.execute_sql(
            "SELECT DISTINCT `home_state` FROM `combined-schedule` WHERE `home_state` IS NOT NULL AND `home_state` != ''"
        )
        if "error" in result:
            click.echo(f"Error fetching states: {result['error']}", err=True)
            return

        rows = result.get("rows", [])
        to_fix = []
        for row in rows:
            val = row.get("home_state", "")
            if not val:
                continue
            val_str = str(val).strip()
            if len(val_str) == 2 and val_str.upper() in US_STATE_CODES:
                continue
            key = val_str.lower()
            if key in STATE_NAME_TO_CODE:
                to_fix.append((val_str, STATE_NAME_TO_CODE[key]))

        if not to_fix:
            click.echo("All home_state values are already 2-letter codes. Nothing to fix.")
            return

        click.echo(f"Found {len(to_fix)} state(s) to normalize:")
        for full_name, code in to_fix:
            click.echo(f"  {full_name} -> {code}")

        if dry_run:
            click.echo("\nDry run - no changes made.")
            return

        click.confirm("Apply these updates to DoltHub?", abort=True)

        updated = 0
        for full_name, code in to_fix:
            escaped = full_name.replace("'", "''")
            sql = f"UPDATE `combined-schedule` SET `home_state` = '{code}' WHERE `home_state` = '{escaped}'"
            r = dolt.execute_sql(sql)
            if "error" in r:
                click.echo(f"Error updating {full_name}: {r['error']}", err=True)
            else:
                updated += 1
                click.echo(f"  Updated {full_name} -> {code}")

        click.echo(f"\nNormalized {updated} state(s).")
