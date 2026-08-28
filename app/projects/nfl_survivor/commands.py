import click
from flask.cli import with_appcontext

from app.projects.nfl_survivor.routes import _fetch_spreads_data
from app.projects.nfl_survivor.utils import get_active_season, is_scheduled_spreads_day


@click.group(name="nfl-survivor")
def nfl_survivor_cli():
    """NFL Survivor pool commands."""


@nfl_survivor_cli.command("fetch-spreads")
@with_appcontext
def fetch_spreads_command():
    """Fetch NFL spreads from The Odds API for the active season."""
    if not is_scheduled_spreads_day():
        click.echo("Skipped: spreads fetch only runs on Tuesday and Thursday (US/Eastern).")
        return

    season = get_active_season()
    if not season:
        raise click.ClickException("No active NFL Survivor season.")

    result = _fetch_spreads_data(season, manual=False)
    if isinstance(result, tuple):
        body, status = result
        msg = body.get("error", body) if isinstance(body, dict) else body
        raise click.ClickException(f"Fetch failed ({status}): {msg}")

    click.echo(result["message"])
    if result.get("remaining_requests") is not None:
        click.echo(f"Odds API quota remaining: {result['remaining_requests']}")


def init_app(app):
    app.cli.add_command(nfl_survivor_cli)
