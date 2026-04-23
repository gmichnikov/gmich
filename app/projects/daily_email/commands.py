"""Flask CLI commands for the Daily Email project."""

import logging
import time
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
    from app.models import LogEntry, User

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

        already_ok = (
            DailyEmailSendLog.query.filter_by(
                user_id=user.id,
                digest_local_date=local_date,
                status="sent",
            ).first()
        )
        if already_ok:
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
    db.session.add(
        LogEntry(
            actor_id=None,
            project="daily_email",
            category="Batch send",
            description=(
                f"sent={sent} failed={failed} already_sent_today={skipped_sent} "
                f"no_credits={skipped_credits} not_due_this_hour={skipped_hour} "
                f"digest_profiles={len(profiles)}"
            ),
        )
    )
    db.session.commit()


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
    Fetch enabled modules, build HTML, send via Mailgun.
    Scheduled sends claim a ``pending`` log row first; credit is decremented only after
    ``send_email`` succeeds. Test sends skip the log and still cost one credit on success.
    """
    from app.models import LogEntry
    from app.projects.daily_email.email_builder import build_digest_html, build_subject
    from app.utils.email_service import send_email

    t_all = time.perf_counter()
    module_results, module_ms, fetch_ms = _fetch_modules_parallel(user, profile)
    t_build = time.perf_counter()
    subject = build_subject(user)
    html = build_digest_html(user, profile, module_results)
    build_ms = (time.perf_counter() - t_build) * 1000.0

    plain = (
        f"Your morning digest is ready. View it in an HTML-capable email client.\n\n"
        f"Manage preferences: {_settings_url()}"
    )

    # Idempotency: claim a 'pending' row before Mailgun. Another worker's claim fails → skip.
    # Credit is only decremented after Mailgun succeeds (2xx from send_email).
    log_row = None
    if not is_test and local_date is not None:
        log_row = _claim_send_log(user.id, local_date)
        if log_row is None:
            logger.warning(
                "daily_email: send log claim conflict for user=%s date=%s — skipping",
                user.id, local_date,
            )
            return False

    db.session.refresh(user)
    if (user.credits or 0) < 1:
        logger.warning(
            "daily_email: credits exhausted after fetch user=%s is_test=%s",
            user.id, is_test,
        )
        if log_row:
            log_row.status = "no_credits"
            log_row.error_summary = "credits<1 at send (race or refund)"
            db.session.commit()
        return False

    t_send = time.perf_counter()
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
        err_text = str(exc)[:500] if exc is not None else "unknown"
        db.session.add(
            LogEntry(
                actor_id=user.id,
                project="daily_email",
                category="Send failed",
                description=f"{'Test send; ' if is_test else ''}Mailgun: {err_text}",
            )
        )
        db.session.commit()
        return False
    else:
        send_ms = (time.perf_counter() - t_send) * 1000.0

    # Success — deduct credit and finalize log (not before Mailgun returns)
    new_c = (user.credits or 0) - 1
    user.credits = max(0, new_c)
    if log_row:
        log_row.status = "sent"
        log_row.sent_at = datetime.utcnow()
        log_row.modules_included = ",".join(
            k for k, v in module_results.items() if v
        )
    db.session.commit()
    total_ms = (time.perf_counter() - t_all) * 1000.0
    logger.info(
        "daily_email: sent user=%s fetch_ms=%.1f modules=%s build_html_ms=%.1f "
        "send_ms=%.1f total_ms=%.1f",
        user.id,
        fetch_ms,
        module_ms,
        build_ms,
        send_ms,
        total_ms,
    )
    return True


def _fetch_modules_parallel(user, profile) -> tuple[dict, dict[str, float], float]:
    """
    Fetch all enabled modules concurrently.
    Returns (module_results, per_module_ms, total_fetch_wall_ms).
    module_results: keys weather/reminders/helper/stocks/sports/jobs; values HTML, ``""``, or None.
    """
    from app.projects.daily_email.modules.digest_reminders import (
        query_upcoming_reminders_for_digest,
        render_reminders_section,
    )
    from app.projects.daily_email.modules.weather import render_weather_section

    rem_list: list = []
    if profile.include_reminders:
        rem_list = query_upcoming_reminders_for_digest(user)

    h_dated: list = []
    h_no: list = []
    if profile.include_helper_tasks:
        from app.projects.daily_email.modules.digest_helper import (
            query_helper_tasks_for_digest,
        )

        h_dated, h_no = query_helper_tasks_for_digest(user)

    tasks: dict = {}

    if profile.include_weather:
        locations = list(
            user.daily_email_weather_locations.order_by(
                _weather_sort_order_col()
            ).all()
        )
        tz = user.time_zone or "UTC"
        tasks["weather"] = (render_weather_section, [locations, tz])

    if profile.include_reminders:
        tasks["reminders"] = (render_reminders_section, [user, rem_list])

    if profile.include_helper_tasks:
        from app.projects.daily_email.modules.digest_helper import render_helper_section

        tasks["helper"] = (render_helper_section, [user, h_dated, h_no])

    if profile.include_stocks:
        from app.projects.daily_email.modules.stocks import render_stocks_section
        stock_tickers = list(
            user.daily_email_stock_tickers.order_by(
                _stock_sort_order_col()
            ).all()
        )
        tasks["stocks"] = (render_stocks_section, [stock_tickers])
    if profile.include_sports:
        from app.projects.daily_email.modules.sports import render_sports_section
        sports_watches = list(
            user.daily_email_sports_watches.order_by(
                _sports_sort_order_col()
            ).all()
        )
        tasks["sports"] = (render_sports_section, [sports_watches, user.time_zone or "UTC"])
    if profile.include_jobs:
        from app.projects.daily_email.modules.jobs import render_jobs_section

        job_watches = list(
            user.daily_email_job_watches.order_by(
                _job_watch_sort_order_col()
            ).all()
        )
        tasks["jobs"] = (render_jobs_section, [job_watches])

    module_ms: dict[str, float] = {}
    results: dict = {}
    t0 = time.perf_counter()

    def _run_module(key, fn, args):
        t_m = time.perf_counter()
        return key, fn(*args), (time.perf_counter() - t_m) * 1000.0

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_run_module, key, fn, args): key
            for key, (fn, args) in tasks.items()
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                mkey, value, ms = future.result()
                results[mkey] = value
                module_ms[mkey] = round(ms, 1)
            except Exception as exc:
                logger.error("daily_email: module %s raised: %s", key, exc, exc_info=True)
                results[key] = None
                module_ms[key] = 0.0

    fetch_ms = (time.perf_counter() - t0) * 1000.0
    if tasks:
        logger.info(
            "daily_email: module_fetch user=%s total_ms=%.1f per_module=%s",
            user.id, fetch_ms, module_ms,
        )
    return results, module_ms, fetch_ms


def _weather_sort_order_col():
    from app.projects.daily_email.models import DailyEmailWeatherLocation
    return DailyEmailWeatherLocation.sort_order


def _stock_sort_order_col():
    from app.projects.daily_email.models import DailyEmailStockTicker
    return DailyEmailStockTicker.sort_order


def _sports_sort_order_col():
    from app.projects.daily_email.models import DailyEmailSportsWatch
    return DailyEmailSportsWatch.sort_order


def _job_watch_sort_order_col():
    from app.projects.daily_email.models import DailyEmailJobWatch
    return DailyEmailJobWatch.sort_order


def _claim_send_log(user_id: int, local_date: date):
    """
    Ensure a 'pending' row for this (user, date) so we only charge credit after send.

    If a row already exists and status is *not* 'sent' (e.g. failed, no_credits, stuck
    pending), remove it and insert fresh pending so a later run or credit fix can retry.
    A row with status 'sent' means the digest for that day was already delivered: returns None.
    """
    from app.projects.daily_email.models import DailyEmailSendLog

    existing = (
        DailyEmailSendLog.query.filter_by(
            user_id=user_id,
            digest_local_date=local_date,
        ).first()
    )
    if existing and existing.status == "sent":
        return None
    if existing and existing.status == "pending":
        return None
    if existing and existing.status in ("failed", "no_credits"):
        db.session.delete(existing)
        db.session.flush()

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
