"""
Flask CLI commands for Sports Schedules.
"""
import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import click
from flask.cli import with_appcontext

from app import db

logger = logging.getLogger(__name__)


def init_app(app):
    app.cli.add_command(sports_schedules_cli)


@click.group(name="sports_schedules")
def sports_schedules_cli():
    """Sports Schedules project commands."""
    pass


@sports_schedules_cli.command("send_digests")
@with_appcontext
def send_digests_command():
    """
    Send weekly digest emails to users whose schedule window is due.
    Runs every Thursday; each user gets one email per week at their chosen hour (±1h).
    Intended to run hourly via Heroku/Render cron.
    """
    from app.core.dolthub_client import DoltHubClient
    from app.projects.sports_schedules.core.config_to_url import config_to_url_params
    from app.projects.sports_schedules.core.query_builder import build_sql
    from app.projects.sports_schedules.core.sample_queries import config_to_params
    from app.projects.sports_schedules.email import send_digest_email
    from app.projects.sports_schedules.models import (
        SportsScheduleScheduledDigest,
        SportsScheduleScheduledDigestQuery,
    )

    now = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")

    digests = (
        SportsScheduleScheduledDigest.query
        .filter(SportsScheduleScheduledDigest.enabled == True)
        .options(
            db.joinedload(SportsScheduleScheduledDigest.user),
            db.selectinload(SportsScheduleScheduledDigest.digest_queries).selectinload(
                SportsScheduleScheduledDigestQuery.saved_query
            ),
        )
        .all()
    )

    sent = 0
    failed = 0
    skipped_reasons = {"not_thursday": 0, "hour_window": 0, "already_sent": 0, "no_credits": 0, "unverified": 0, "no_queries": 0}

    for digest in digests:
        # Must have at least one digest query
        valid_dqs = [dq for dq in digest.digest_queries if dq.saved_query and dq.saved_query.user_id == digest.user_id]
        if not valid_dqs:
            skipped_reasons["no_queries"] += 1
            continue

        user = digest.user
        try:
            tz = ZoneInfo(user.time_zone or "UTC")
        except Exception:
            tz = ZoneInfo("UTC")
        user_local = now.astimezone(tz)
        weekday = user_local.weekday()  # Mon=0, Thu=3
        current_hour = user_local.hour

        if weekday != 3:
            skipped_reasons["not_thursday"] += 1
            continue

        hour_min = max(0, digest.schedule_hour - 1)
        hour_max = min(23, digest.schedule_hour + 1)
        if current_hour < hour_min or current_hour > hour_max:
            skipped_reasons["hour_window"] += 1
            continue

        # Check last_sent_at: same Thursday?
        if digest.last_sent_at:
            last_sent_local = digest.last_sent_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
            if last_sent_local.date() == user_local.date():
                skipped_reasons["already_sent"] += 1
                continue

        if (user.credits or 0) < 1:
            skipped_reasons["no_credits"] += 1
            continue

        if not user.email_verified:
            skipped_reasons["unverified"] += 1
            continue

        thursday_ymd = user_local.strftime("%Y-%m-%d")
        query_results = []
        dolt = DoltHubClient()

        for dq in valid_dqs:
            sq = dq.saved_query
            config = json.loads(sq.config) if isinstance(sq.config, str) else sq.config
            params = config_to_params(config, anchor_date=thursday_ymd)
            params["limit"] = 25

            url = config_to_url_params(config, base_url, anchor_date=thursday_ymd)

            sql, err = build_sql(params)
            if err:
                query_results.append({"name": sq.name, "rows": [], "count": False, "url": url, "error": err})
                continue

            result = dolt.execute_sql(sql)
            if "error" in result:
                query_results.append({"name": sq.name, "rows": [], "count": params.get("count", False), "url": url, "error": result["error"]})
                continue

            rows = result.get("rows", [])[:25]
            query_results.append({"name": sq.name, "rows": rows, "count": params.get("count", False), "url": url, "error": None})

        if not query_results:
            continue

        try:
            send_digest_email(digest, query_results)
            digest.last_sent_at = datetime.utcnow()
            user.credits = (user.credits or 0) - 1
            db.session.commit()
            sent += 1
            logger.info(f"Sent digest {digest.id} to {user.email}")
        except Exception as e:
            db.session.rollback()
            failed += 1
            logger.error(f"Failed to send digest {digest.id}: {e}")

    parts = [f"Digests: {sent} sent, {failed} failed"]
    if any(skipped_reasons.values()):
        parts.append(f"skipped: {sum(skipped_reasons.values())} ({dict((k, v) for k, v in skipped_reasons.items() if v)})")
    click.echo(", ".join(parts))
