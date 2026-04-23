"""Flask CLI commands for the Daily Email project."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date
from zoneinfo import ZoneInfo

import click
from flask.cli import with_appcontext
from sqlalchemy.exc import IntegrityError

from app import db

logger = logging.getLogger(__name__)


def init_app(app):
    app.cli.add_command(daily_email_cli)


@click.group(name="daily_email")
def daily_email_cli():
    """Daily Email project commands."""
    pass


# ---------------------------------------------------------------------------
# Scheduled send (runs every hour via Heroku Scheduler)
# ---------------------------------------------------------------------------

@daily_email_cli.command("send")
@with_appcontext
def send_command():
    """
    Send digests to all users who are due in the current hour.
    Intended to run once per hour via Heroku Scheduler.
    """
    from app.projects.daily_email.models import DailyEmailProfile, DailyEmailSendLog
    from app.models import User

    profiles = (
        DailyEmailProfile.query
        .filter_by(digest_enabled=True)
        .join(User, User.id == DailyEmailProfile.user_id)
        .all()
    )

    sent = failed = skipped_hour = skipped_sent = skipped_credits = 0

    for profile in profiles:
        user = profile.user
        user_tz = ZoneInfo(user.time_zone or "UTC")
        now_local = datetime.now(user_tz)
        local_date = now_local.date()
        local_hour = now_local.hour

        if local_hour != profile.send_hour_local:
            skipped_hour += 1
            continue

        already_sent = DailyEmailSendLog.query.filter_by(
            user_id=user.id,
            digest_local_date=local_date,
        ).first()
        if already_sent:
            skipped_sent += 1
            continue

        if (user.credits or 0) < 1:
            skipped_credits += 1
            _log_send(user.id, local_date, "no_credits")
            continue

        result = _build_and_send(user, profile, local_date)
        if result:
            sent += 1
        else:
            failed += 1

    click.echo(
        f"Daily email send complete: {sent} sent, {failed} failed, "
        f"{skipped_sent} already sent today, {skipped_credits} skipped (no credits), "
        f"{skipped_hour} not due this hour."
    )


# ---------------------------------------------------------------------------
# On-demand test send
# ---------------------------------------------------------------------------

@daily_email_cli.command("send_test")
@click.option("--user-id", type=int, required=True, help="User ID to send test digest to.")
@with_appcontext
def send_test_command(user_id):
    """
    Send a one-off test digest to a specific user immediately.
    Costs one credit. Does NOT insert a send log row (scheduled send still fires later).
    """
    from app.projects.daily_email.models import DailyEmailProfile
    from app.models import User

    user = User.query.get(user_id)
    if not user:
        click.echo(f"No user found with id={user_id}", err=True)
        return

    profile = DailyEmailProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        click.echo(f"User {user_id} has no DailyEmailProfile. Create one first.", err=True)
        return

    if (user.credits or 0) < 1:
        click.echo(f"User {user_id} has 0 credits — cannot send.", err=True)
        return

    click.echo(f"Sending test digest to {user.email} ...")
    ok = _build_and_send(user, profile, local_date=None, is_test=True)
    if ok:
        click.echo("Test digest sent successfully.")
    else:
        click.echo("Test digest failed — check logs.", err=True)


# ---------------------------------------------------------------------------
# Shared build + send logic
# ---------------------------------------------------------------------------

def _build_and_send(user, profile, local_date: date | None, is_test: bool = False) -> bool:
    """
    Fetch all enabled modules in parallel, build the HTML digest, send via Mailgun.
    On success: deduct 1 credit and (unless test) insert send log row.
    Returns True on success, False on failure.
    """
    from app.projects.daily_email.email_builder import build_digest_html, build_subject
    from app.utils.email_service import send_email

    module_results = _fetch_modules_parallel(user, profile)

    subject = build_subject(user)
    html = build_digest_html(user, profile, module_results)

    plain = (
        f"Your morning digest is ready. View it in an HTML-capable email client.\n\n"
        f"Manage preferences: {_settings_url()}"
    )

    # Claim a send log row before calling Mailgun (idempotency for scheduled sends)
    log_row = None
    if not is_test and local_date is not None:
        log_row = _claim_send_log(user.id, local_date)
        if log_row is None:
            logger.warning(
                "daily_email: send log claim conflict for user=%s date=%s — skipping",
                user.id, local_date,
            )
            return False

    try:
        send_email(
            to_email=user.email,
            subject=subject,
            text_content=plain,
            html_content=html,
            from_name="Daily Digest",
        )
    except Exception as exc:
        logger.error("daily_email: Mailgun send failed for user=%s: %s", user.id, exc)
        if log_row:
            log_row.status = "failed"
            log_row.error_summary = str(exc)[:500]
            db.session.commit()
        return False

    # Success — deduct credit and finalize log
    user.credits = (user.credits or 0) - 1
    if log_row:
        log_row.status = "sent"
        log_row.sent_at = datetime.utcnow()
        log_row.modules_included = ",".join(
            k for k, v in module_results.items() if v is not None
        )
    db.session.commit()
    logger.info("daily_email: sent digest to user=%s", user.id)
    return True


def _fetch_modules_parallel(user, profile) -> dict:
    """
    Fetch all enabled modules concurrently.
    Returns dict with keys weather/stocks/sports/jobs; value is HTML string or None.
    """
    from app.projects.daily_email.modules.weather import render_weather_section

    tasks = {}

    if profile.include_weather:
        locations = list(
            user.daily_email_weather_locations.order_by(
                _weather_sort_order_col()
            ).all()
        )
        tasks["weather"] = (render_weather_section, [locations])

    # Stocks, sports, jobs placeholders — modules added in later phases
    if profile.include_stocks:
        tasks["stocks"] = (_not_implemented_yet, ["stocks"])
    if profile.include_sports:
        tasks["sports"] = (_not_implemented_yet, ["sports"])
    if profile.include_jobs:
        tasks["jobs"] = (_not_implemented_yet, ["jobs"])

    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(fn, *args): key
            for key, (fn, args) in tasks.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as exc:
                logger.error("daily_email: module %s raised: %s", key, exc)
                results[key] = None

    return results


def _not_implemented_yet(_key) -> None:
    """Placeholder until the module is built in a later phase."""
    return None


def _weather_sort_order_col():
    from app.projects.daily_email.models import DailyEmailWeatherLocation
    return DailyEmailWeatherLocation.sort_order


def _claim_send_log(user_id: int, local_date: date):
    """
    Insert a 'pending' send log row. Returns the row on success, None on conflict.
    Uses a savepoint so the outer transaction is not poisoned on IntegrityError.
    """
    from app.projects.daily_email.models import DailyEmailSendLog

    row = DailyEmailSendLog(
        user_id=user_id,
        digest_local_date=local_date,
        status="pending",
    )
    try:
        db.session.add(row)
        db.session.flush()
        return row
    except IntegrityError:
        db.session.rollback()
        return None


def _log_send(user_id: int, local_date: date, status: str):
    """Insert a terminal (non-pending) send log row, ignoring conflicts."""
    from app.projects.daily_email.models import DailyEmailSendLog

    row = DailyEmailSendLog(
        user_id=user_id,
        digest_local_date=local_date,
        status=status,
    )
    try:
        db.session.add(row)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


def _settings_url() -> str:
    import os
    base = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    return f"{base}/daily-email/settings"
