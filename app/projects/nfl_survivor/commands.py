import click
from flask.cli import with_appcontext

from app import db
from app.projects.nfl_survivor.log import log_nfl_survivor
from app.projects.nfl_survivor.routes import _fetch_spreads_data
from app.projects.nfl_survivor.schedule import fetch_schedule_for_active_weeks
from app.projects.nfl_survivor.utils import get_active_season, is_scheduled_spreads_day


@click.group(name="nfl-survivor")
def nfl_survivor_cli():
    """NFL Survivor pool commands."""


@nfl_survivor_cli.command("fetch-schedule")
@with_appcontext
def fetch_schedule_command():
    """Fetch NFL kickoff times from ESPN for the active season."""
    season = get_active_season()
    if not season:
        raise click.ClickException("No active NFL Survivor season.")

    try:
        total, weeks = fetch_schedule_for_active_weeks(season, source="cron")
    except Exception as exc:
        log_nfl_survivor(
            "Fetch Schedule",
            f"Cron fetch schedule failed ({season.name}): {exc}",
            actor_id=None,
        )
        db.session.commit()
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Updated schedule for weeks {weeks}: {total} team rows.")


@nfl_survivor_cli.command("fetch-spreads")
@with_appcontext
def fetch_spreads_command():
    """Fetch NFL spreads from The Odds API for the active season."""
    if not is_scheduled_spreads_day():
        log_nfl_survivor(
            "Fetch Spreads",
            "Cron fetch-spreads skipped (not Tuesday or Thursday, US/Eastern)",
            actor_id=None,
        )
        db.session.commit()
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


@nfl_survivor_cli.command("sync")
@with_appcontext
def sync_command():
    """Daily job: always refresh schedule; refresh spreads on Tue/Thu."""
    season = get_active_season()
    if not season:
        raise click.ClickException("No active NFL Survivor season.")

    try:
        total, weeks = fetch_schedule_for_active_weeks(season, source="cron")
    except Exception as exc:
        log_nfl_survivor(
            "Fetch Schedule",
            f"Cron sync schedule fetch failed ({season.name}): {exc}",
            actor_id=None,
        )
        db.session.commit()
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Schedule weeks {weeks}: {total} team rows.")

    if is_scheduled_spreads_day():
        result = _fetch_spreads_data(season, manual=False)
        if isinstance(result, tuple):
            body, status = result
            msg = body.get("error", body) if isinstance(body, dict) else body
            raise click.ClickException(f"Spreads fetch failed ({status}): {msg}")
        click.echo(result["message"])
    else:
        log_nfl_survivor(
            "Sync",
            (
                f"Cron sync: schedule updated for weeks {weeks}; spreads skipped "
                f"(not Tuesday or Thursday, US/Eastern) ({season.name})"
            ),
            actor_id=None,
        )
        db.session.commit()
        click.echo("Spreads skipped (not Tuesday or Thursday, US/Eastern).")


def init_app(app):
    app.cli.add_command(nfl_survivor_cli)
