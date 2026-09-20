"""Sunday missing-pick nudge: mandatory, independent of reminder prefs."""

from __future__ import annotations

import html
import logging
import os
from collections import defaultdict
from datetime import datetime

from sqlalchemy.orm import joinedload

from app import db
from app.models import LogEntry
from app.projects.nfl_survivor.log import PROJECT, log_nfl_survivor
from app.projects.nfl_survivor.models import NflSurvivorParticipant, NflSurvivorPick
from app.projects.nfl_survivor.utils import EASTERN, get_active_season, get_current_pick_week

logger = logging.getLogger(__name__)

SUNDAY_WEEKDAY = 6
SUNDAY_NUDGE_CATEGORY = "Sunday Nudge"


def _now_eastern(when=None):
    if when is None:
        return datetime.now(EASTERN)
    if when.tzinfo is None:
        return EASTERN.localize(when)
    return when.astimezone(EASTERN)


def is_sunday(now_eastern):
    return now_eastern.weekday() == SUNDAY_WEEKDAY


def sunday_nudge_log_prefix(season_name, week):
    return f"Week {week} missing-pick nudge ({season_name})"


def sunday_nudge_already_logged(descriptions, season_name, week):
    prefix = sunday_nudge_log_prefix(season_name, week)
    return any((description or "").startswith(prefix) for description in descriptions)


def sunday_nudge_subject(week):
    return f"NFL Survivor — you still need a Week {week} pick"


def sunday_nudge_text(week, pick_url, missing_names, list_entries):
    lines = [
        f"You have not submitted an NFL Survivor pick for week {week}.",
        "",
    ]
    if list_entries and missing_names:
        lines.append("Still need a pick:")
        lines.extend(f"- {name}" for name in missing_names)
        lines.append("")
    lines.append(f"Make your pick: {pick_url}")
    return "\n".join(lines)


def sunday_nudge_html(week, pick_url, missing_names, list_entries):
    names_html = ""
    if list_entries and missing_names:
        items = "".join(
            f"<li>{html.escape(name)}</li>" for name in missing_names
        )
        names_html = (
            '<p style="margin:0 0 8px 0;font-weight:600;">Still need a pick:</p>'
            f'<ul style="margin:0 0 16px 0;padding-left:20px;">{items}</ul>'
        )
    return f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #1a1f2e; }}
        .ns-mail-container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
    </style>
</head>
<body>
    <div class="ns-mail-container">
        <h2 style="margin:0 0 12px 0;color:#013369;">NFL Survivor</h2>
        <p style="margin:0 0 16px 0;">
            You have not submitted a pick for week {week}.
        </p>
        {names_html}
        <p style="margin:24px 0 8px 0;">
            <a href="{html.escape(pick_url, quote=True)}"
               style="display:inline-block;padding:12px 20px;background-color:#013369;
               color:#ffffff !important;text-decoration:none;border-radius:6px;
               font-weight:bold;">Make your pick</a>
        </p>
        <p style="margin:0;font-size:13px;color:#5c6578;">
            Picks lock when that team's game starts.
        </p>
    </div>
</body>
</html>
"""


def missing_entry_names(
    entries, picks_by_entry, wrong_counts, current_week, pick_week_open
):
    """Display names of alive entries that still need a pick this week."""
    if not pick_week_open:
        return []
    missing = []
    for entry in entries:
        if wrong_counts.get(entry.id, 0) >= 2:
            continue
        entry_picks = picks_by_entry.get(entry.id, [])
        if any(pick.week == current_week for pick in entry_picks):
            continue
        missing.append(entry.display_name)
    return missing


def collect_nudge_recipients(
    participants,
    picks_by_entry,
    wrong_counts,
    current_week,
    pick_week_open,
    users_by_id,
):
    """
    Unique users with at least one alive entry and no pick this week.

    Skips unverified emails. list_entries is True when the user has more
    than one entry in the pool.
    """
    by_user = defaultdict(list)
    for participant in participants:
        by_user[participant.user_id].append(participant)

    recipients = []
    skipped_unverified = 0
    for user_id, entries in by_user.items():
        missing_names = missing_entry_names(
            entries,
            picks_by_entry,
            wrong_counts,
            current_week,
            pick_week_open,
        )
        if not missing_names:
            continue
        user = users_by_id.get(user_id)
        if user is None or not user.email:
            continue
        if not user.email_verified:
            skipped_unverified += 1
            continue
        recipients.append(
            {
                "user": user,
                "email": user.email,
                "missing_names": missing_names,
                "list_entries": len(entries) > 1,
            }
        )

    recipients.sort(key=lambda row: (row["email"] or "").lower())
    return recipients, skipped_unverified


def _load_nudge_rows(season):
    current_week = get_current_pick_week(season)
    pick_week_open = current_week <= season.max_weeks
    participants = (
        NflSurvivorParticipant.query.filter_by(season_id=season.id)
        .options(joinedload(NflSurvivorParticipant.user))
        .all()
    )
    picks = NflSurvivorPick.query.filter_by(season_id=season.id).all()
    picks_by_entry = defaultdict(list)
    for pick in picks:
        picks_by_entry[pick.participant_id].append(pick)

    wrong_counts = {}
    for participant_id, entry_picks in picks_by_entry.items():
        wrong_counts[participant_id] = sum(
            1 for pick in entry_picks if pick.is_correct is False
        )

    users_by_id = {}
    for participant in participants:
        if participant.user is not None:
            users_by_id[participant.user_id] = participant.user

    return {
        "current_week": current_week,
        "pick_week_open": pick_week_open,
        "participants": participants,
        "picks_by_entry": picks_by_entry,
        "wrong_counts": wrong_counts,
        "users_by_id": users_by_id,
    }


def _logged_nudge_descriptions(season_name, week):
    prefix = sunday_nudge_log_prefix(season_name, week)
    rows = (
        LogEntry.query.filter_by(project=PROJECT, category=SUNDAY_NUDGE_CATEGORY)
        .filter(LogEntry.description.startswith(prefix))
        .all()
    )
    return [row.description for row in rows]


def _admin_bcc(recipient_email):
    admin_email = (os.getenv("ADMIN_EMAIL") or "").strip()
    if not admin_email:
        return None
    if recipient_email and admin_email.lower() == recipient_email.lower():
        return None
    return admin_email


def run_sunday_nudge(*, when=None, dry_run=False):
    """
    Send the Sunday missing-pick nudge for the active season.

    dry_run: print who would be emailed; skip Sunday/log guards so you can
    preview any day. Does not send or write the sent log.
    """
    from app.projects.nfl_survivor.email import send_sunday_nudge_email

    season = get_active_season()
    if not season:
        return {"error": "No active NFL Survivor season."}

    now_eastern = _now_eastern(when)
    result = {
        "week": None,
        "recipients": 0,
        "sent": 0,
        "failed": 0,
        "dry_run": dry_run,
        "skipped_day": 0,
        "skipped_already": 0,
        "skipped_empty": 0,
        "skipped_unverified": 0,
    }

    if not dry_run and not is_sunday(now_eastern):
        result["skipped_day"] = 1
        return result

    data = _load_nudge_rows(season)
    week = data["current_week"]
    result["week"] = week

    if not dry_run and sunday_nudge_already_logged(
        _logged_nudge_descriptions(season.name, week), season.name, week
    ):
        result["skipped_already"] = 1
        return result

    recipients, skipped_unverified = collect_nudge_recipients(
        data["participants"],
        data["picks_by_entry"],
        data["wrong_counts"],
        week,
        data["pick_week_open"],
        data["users_by_id"],
    )
    result["skipped_unverified"] = skipped_unverified
    result["recipients"] = len(recipients)

    if not recipients:
        result["skipped_empty"] = 1
        return result

    if dry_run:
        return result

    sent_emails = []
    for row in recipients:
        try:
            send_sunday_nudge_email(
                row["user"],
                week,
                missing_names=row["missing_names"],
                list_entries=row["list_entries"],
                bcc=_admin_bcc(row["email"]),
            )
            sent_emails.append(row["email"])
        except Exception:
            logger.exception("Sunday nudge failed for %s", row["email"])
            result["failed"] += 1

    result["sent"] = len(sent_emails)
    if sent_emails:
        emails_preview = ", ".join(sent_emails)
        log_nfl_survivor(
            SUNDAY_NUDGE_CATEGORY,
            (
                f"{sunday_nudge_log_prefix(season.name, week)}: "
                f"sent to {len(sent_emails)} "
                f"{'person' if len(sent_emails) == 1 else 'people'} "
                f"({emails_preview})"
            ),
            actor_id=None,
        )
        db.session.commit()
    return result
