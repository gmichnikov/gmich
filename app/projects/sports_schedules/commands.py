"""
Flask CLI commands for Sports Schedules.
"""
import csv
import json
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import click
from flask.cli import with_appcontext

from app import db

logger = logging.getLogger(__name__)


def _digest_query_result(sq, anchor_ymd: str, base_url: str, dolt):
    """Run one saved query for a digest email; matches /api/query distance behavior."""
    from app.projects.sports_schedules.core.config_to_url import config_to_url_params
    from app.projects.sports_schedules.core.distance_prepare import (
        apply_post_sql_distance,
        prepare_distance_filter,
    )
    from app.projects.sports_schedules.core.query_builder import build_sql
    from app.projects.sports_schedules.core.sample_queries import config_to_params

    DIGEST_ROWS_IN_EMAIL = 25
    SQL_CANDIDATE_CAP = 500

    config = json.loads(sq.config) if isinstance(sq.config, str) else sq.config
    params = config_to_params(config, anchor_date=anchor_ymd)
    url = config_to_url_params(config, base_url, anchor_date=anchor_ymd)

    dpr = prepare_distance_filter(params)
    if dpr.error:
        return {
            "name": sq.name,
            "rows": [],
            "count": params.get("count", False),
            "url": url,
            "error": dpr.error,
        }
    if dpr.early_empty:
        return {
            "name": sq.name,
            "rows": [],
            "count": params.get("count", False),
            "url": url,
            "error": None,
        }

    # Distance runs in Python after SQL; only N SQL rows enter the funnel. Match the
    # interactive UI candidate pool so the digest isn’t artificially sparse.
    if dpr.distance_filter_active and not params.get("count"):
        params["limit"] = SQL_CANDIDATE_CAP
    else:
        params["limit"] = DIGEST_ROWS_IN_EMAIL

    sql, err = build_sql(params)
    if err:
        return {
            "name": sq.name,
            "rows": [],
            "count": params.get("count", False),
            "url": url,
            "error": err,
        }

    result = dolt.execute_sql(sql)
    if "error" in result:
        return {
            "name": sq.name,
            "rows": [],
            "count": params.get("count", False),
            "url": url,
            "error": result["error"],
        }

    rows = result.get("rows", [])
    rows = apply_post_sql_distance(rows, params, dpr)
    rows = rows[:DIGEST_ROWS_IN_EMAIL]
    return {
        "name": sq.name,
        "rows": rows,
        "count": params.get("count", False),
        "url": url,
        "error": None,
    }


def send_digest_immediately(digest):
    """
    Send a digest email immediately, bypassing Thursday/hour checks.
    Used for admin testing. Returns (success: bool, error: str | None).
    """
    from app.core.dolthub_client import DoltHubClient
    from app.projects.sports_schedules.email import send_digest_email

    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    user = digest.user
    try:
        tz = ZoneInfo(user.time_zone or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")
    now = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
    user_local = now.astimezone(tz)
    anchor_ymd = user_local.strftime("%Y-%m-%d")

    valid_dqs = [dq for dq in digest.digest_queries if dq.saved_query and dq.saved_query.user_id == digest.user_id]
    if not valid_dqs:
        return False, "No saved queries in digest"

    if (user.credits or 0) < 1:
        return False, "Insufficient credits"

    if not user.email_verified:
        return False, "Email not verified"

    query_results = []
    dolt = DoltHubClient()
    for dq in valid_dqs:
        query_results.append(_digest_query_result(dq.saved_query, anchor_ymd, base_url, dolt))

    if not query_results:
        return False, "No query results"

    try:
        send_digest_email(digest, query_results)
        digest.last_sent_at = datetime.utcnow()
        user.credits = (user.credits or 0) - 1
        db.session.commit()
        logger.info(f"Sent digest {digest.id} to {user.email} (test)")
        return True, None
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to send digest {digest.id}: {e}")
        return False, str(e)


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
            query_results.append(
                _digest_query_result(dq.saved_query, thursday_ymd, base_url, dolt)
            )

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


@sports_schedules_cli.command("import-zips")
@click.argument("filepath", type=click.Path(exists=True))
@with_appcontext
def import_zips_command(filepath):
    """
    Import simplemaps uszips.csv into the ss_zip_codes table.
    Usage: flask sports_schedules import-zips /path/to/uszips.csv
    """
    from app.projects.sports_schedules.models import SportsScheduleZipCode

    inserted = 0
    skipped = 0
    batch_size = 500

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            try:
                lat = float(row["lat"])
                lon = float(row["lng"])
            except (ValueError, KeyError):
                skipped += 1
                continue

            zip_val = row.get("zip", "").strip()
            city = row.get("city", "").strip()
            state_id = row.get("state_id", "").strip()

            if not zip_val or not state_id:
                skipped += 1
                continue

            batch.append(
                SportsScheduleZipCode(
                    zip=zip_val,
                    city=city,
                    state_id=state_id,
                    lat=lat,
                    lon=lon,
                )
            )

            if len(batch) >= batch_size:
                db.session.bulk_save_objects(batch)
                db.session.commit()
                inserted += len(batch)
                batch = []

        if batch:
            db.session.bulk_save_objects(batch)
            db.session.commit()
            inserted += len(batch)

    click.echo(f"Done: {inserted} zip codes imported, {skipped} rows skipped.")


@sports_schedules_cli.command("warm-geocache")
@with_appcontext
def warm_geocache_command():
    """
    Pre-populate ss_geocode_cache with all distinct city/state pairs from DoltHub.
    Safe to run multiple times — skips pairs already cached.
    Usage: flask sports_schedules warm-geocache
    """
    from app.core.dolthub_client import DoltHubClient
    from app.projects.sports_schedules.core.geocode import citystate_to_coords
    from app.projects.sports_schedules.models import SportsScheduleGeocodeCache

    result = DoltHubClient().execute_sql(
        "SELECT DISTINCT home_city, home_state FROM `combined-schedule` "
        "WHERE home_city IS NOT NULL AND home_city != ''"
    )
    if "error" in result:
        click.echo(f"Error querying DoltHub: {result['error']}")
        return

    pairs = [
        (r.get("home_city", "").strip(), r.get("home_state", "").strip())
        for r in result.get("rows", [])
        if r.get("home_city", "").strip()
    ]

    already_cached = {
        (r.city, r.state)
        for r in SportsScheduleGeocodeCache.query.all()
    }

    to_geocode = [p for p in pairs if p not in already_cached]
    click.echo(f"Found {len(pairs)} distinct city/state pairs, {len(to_geocode)} not yet cached.")

    geocoded = 0
    failed = 0
    for city, state in to_geocode:
        coords = citystate_to_coords(city, state)
        if coords:
            geocoded += 1
        else:
            failed += 1
        click.echo(f"  {'OK' if coords else 'MISS'} {city!r}, {state!r}")

    click.echo(f"Done: {geocoded} geocoded, {failed} misses (stored as null coords).")


@sports_schedules_cli.command("agent-query")
@click.option("--zip", "zip_code", default=None, help="Zip code for radius search (e.g. 07928)")
@click.option("--radius", default=50.0, type=float, help="Radius in miles (default: 50)")
@click.option("--days", default=7, type=int, help="Number of days forward to search (default: 7)")
@click.option("--team", multiple=True, help="Optional team filter (can specify multiple)")
@click.option("--league", multiple=True, help="Optional league filter (can specify multiple)")
@click.option("--sport", multiple=True, help="Optional sport filter (can specify multiple)")
@click.option("--limit", default=200, type=int, help="Max results (default: 200)")
@with_appcontext
def agent_query_command(zip_code, radius, days, team, league, sport, limit):
    """
    Fetch upcoming games in clean JSON format for automated agents.
    Supports distance/zip filtering, league/sport filtering, and team matching.
    """
    from app.core.dolthub_client import DoltHubClient
    from app.projects.sports_schedules.core.distance_prepare import (
        apply_post_sql_distance,
        prepare_distance_filter,
    )
    from app.projects.sports_schedules.core.query_builder import build_sql

    now = datetime.utcnow()
    start_ymd = now.strftime("%Y-%m-%d")
    end_ymd = (now + timedelta(days=days)).strftime("%Y-%m-%d")

    filters = {}
    if team:
        filters["either_team"] = list(team)
    if league:
        filters["league"] = list(league)
    if sport:
        filters["sport"] = list(sport)

    params = {
        "dimensions": "date,time,home_team,road_team,location,home_city,home_state,sport,league,level",
        "filters": filters,
        "date_mode": "next_n",
        "date_n": days,
        "anchor_date": start_ymd,
        "limit": min(limit * 2, 2000),  # extra buffer for distance filter post-processing
        "sort_column": "date",
        "sort_dir": "asc",
    }

    if zip_code:
        params["zip_code"] = zip_code
        params["radius_miles"] = radius

    dpr = prepare_distance_filter(params)
    if dpr.error:
        click.echo(json.dumps({"error": dpr.error}))
        return
    if dpr.early_empty:
        click.echo(json.dumps({"rows": [], "count": 0}))
        return

    if dpr.distance_filter_active and not params.get("count"):
        params["limit"] = max(limit * 2, 500)
    else:
        params["limit"] = limit

    sql, err = build_sql(params)
    if err:
        click.echo(json.dumps({"error": err}))
        return

    dolt = DoltHubClient()
    result = dolt.execute_sql(sql)
    if "error" in result:
        click.echo(json.dumps({"error": result["error"]}))
        return

    rows = result.get("rows", [])
    if dpr.distance_filter_active:
        rows = apply_post_sql_distance(rows, params, dpr)

    rows = rows[:limit]
    click.echo(json.dumps({"rows": rows, "count": len(rows)}, indent=2))


@sports_schedules_cli.command("agent-email")
@click.option("--to", "to_email", required=True, help="Recipient email address")
@click.option("--subject", required=True, help="Subject line")
@click.option("--body", "body_text", default=None, help="Plain text body (optional if passing markdown/html)")
@click.option("--html", "body_html", default=None, help="HTML body (optional)")
@with_appcontext
def agent_email_command(to_email, subject, body_text, body_html):
    """
    Send an email via the app's configured Mailgun service.
    Accepts plain text, HTML, or reads body from stdin if not provided via options.
    """
    import sys
    from app.utils.email_service import send_email

    if not body_text and not body_html:
        if not sys.stdin.isatty():
            body_text = sys.stdin.read()
        else:
            click.echo("Error: Please provide --body or pipe text via stdin.", err=True)
            sys.exit(1)

    text_content = body_text or "Please see the HTML version of this message."
    html_content = body_html

    try:
        send_email(
            to_email=to_email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            from_name="Sports Schedule Curator",
        )
        click.echo(f"Successfully sent email to {to_email}")
    except Exception as e:
        click.echo(f"Failed to send email: {e}", err=True)
        sys.exit(1)

