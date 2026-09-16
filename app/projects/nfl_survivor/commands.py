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


@nfl_survivor_cli.command("send-reminders")
@click.option("--user-id", type=int, default=None, help="Only this user id.")
@click.option("--email", "user_email", default=None, help="Only this user email.")
@click.option(
    "--force",
    is_flag=True,
    help="Ignore weekday and last-sent; do not mark as sent. Requires --user-id or --email.",
)
@click.option("--dry-run", is_flag=True, help="Print counts without sending.")
@with_appcontext
def send_reminders_command(user_id, user_email, force, dry_run):
    """Send reminder emails to users whose chosen weekday is today (US/Eastern)."""
    from app.models import User
    from app.projects.nfl_survivor.reminders import run_reminder_send

    if user_email:
        user = User.query.filter_by(email=user_email).first()
        if not user:
            raise click.ClickException(f"No user with email {user_email}.")
        if user_id is not None and user.id != user_id:
            raise click.ClickException("--user-id and --email do not match.")
        user_id = user.id

    if force and user_id is None:
        raise click.ClickException("--force requires --user-id or --email.")

    result = run_reminder_send(
        user_id=user_id, force=force, dry_run=dry_run
    )
    if result.get("error"):
        raise click.ClickException(result["error"])

    click.echo(
        "candidates={candidates} sent={sent} failed={failed} "
        "dry_run={dry_run} skipped_day={skipped_day} "
        "skipped_already={skipped_already} skipped_empty={skipped_empty} "
        "skipped_unverified={skipped_unverified}".format(**result)
    )


def init_app(app):
    app.cli.add_command(nfl_survivor_cli)
