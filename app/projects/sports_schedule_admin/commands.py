import click
from datetime import datetime, timedelta
from app.projects.sports_schedule_admin.core.logic import sync_league_range

def init_app(app):
    """Register CLI commands with the Flask app"""

    @app.cli.group("sports-admin")
    def sports_admin():
        """Sports Schedule Admin commands"""
        pass

    @sports_admin.command("sync")
    @click.option("--league", required=True, help="League code (MLB, NBA, NFL, NHL, MLS, EPL)")
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
        leagues = ["MLB", "NBA", "NFL", "NHL", "MLS", "EPL"]
        start_dt = datetime.now()
        end_dt = start_dt + timedelta(days=7)
        
        click.echo(f"Starting daily sync for all leagues from {start_dt.date()} to {end_dt.date()}...")
        
        for league in leagues:
            click.echo(f"Syncing {league}...")
            result = sync_league_range(league, start_dt, end_dt)
            click.echo(f"  {league}: {result['upserted']} games updated.")
        
        click.echo("Daily sync complete.")

    @sports_admin.command("clear-league")
    @click.option("--league", required=True, help="League code to clear")
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
