"""Build and send NFL Survivor reminder emails."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy.orm import joinedload

from app import db
from app.models import User
from app.projects.nfl_survivor.log import log_nfl_survivor
from app.projects.nfl_survivor.models import (
    NflSurvivorEmailPref,
    NflSurvivorParticipant,
    NflSurvivorPick,
    NflSurvivorSpread,
    NflSurvivorWeeklyResult,
)
from app.projects.nfl_survivor.utils import (
    EASTERN,
    UTC,
    format_pick_outcome,
    get_current_pick_week,
    is_week_picks_revealed,
    load_nfl_teams_as_dict,
)

logger = logging.getLogger(__name__)


def classify_entry(wrong_picks, elimination_email_sent_at):
    """alive, new_out (first elimination notice), or skip."""
    if wrong_picks >= 2:
        if elimination_email_sent_at:
            return "skip"
        return "new_out"
    return "alive"


def already_sent_today(last_sent_at, now_eastern):
    if last_sent_at is None:
        return False
    sent = last_sent_at
    if sent.tzinfo is None:
        sent = UTC.localize(sent)
    else:
        sent = sent.astimezone(UTC)
    return sent.astimezone(EASTERN).date() == now_eastern.date()


def should_send_pref(reminder_weekday, today_weekday, last_sent_at, now_eastern, *, force=False):
    if force:
        return True
    if reminder_weekday is None:
        return False
    if reminder_weekday != today_weekday:
        return False
    if already_sent_today(last_sent_at, now_eastern):
        return False
    return True


def reminder_subject(payload):
    entries = payload.get("entries") or []
    if entries and all(entry["status"] == "eliminated" for entry in entries):
        return "NFL Survivor — an entry is out"
    return f"NFL Survivor — Week {payload['current_week']} update"


def format_pick_count_line(counts):
    if not counts:
        return ""
    parts = [f"{name} ({n})" for name, n in counts]
    return ", ".join(parts)


def _now_eastern(when=None):
    if when is None:
        return datetime.now(EASTERN)
    if when.tzinfo is None:
        return EASTERN.localize(when)
    return when.astimezone(EASTERN)


def _last_week_pick_line(pick, team_lookup, matchup_by_name, result_by_team):
    if pick is None:
        return None, None
    team_name = team_lookup.get(pick.team, pick.team)
    opponent = matchup_by_name.get(team_name)
    result = result_by_team.get(pick.team)
    outcome = format_pick_outcome(result, opponent)
    if not outcome:
        outcome = "Result pending"
    return team_name, outcome


def load_reminder_season_data(season):
    current_week = get_current_pick_week(season)
    last_week = current_week - 1 if current_week > 1 else None
    participants = NflSurvivorParticipant.query.filter_by(season_id=season.id).all()
    picks = NflSurvivorPick.query.filter_by(season_id=season.id).all()
    picks_by_entry = defaultdict(list)
    for pick in picks:
        picks_by_entry[pick.participant_id].append(pick)

    team_lookup = load_nfl_teams_as_dict()
    last_week_revealed = last_week is not None and is_week_picks_revealed(
        season, last_week
    )

    matchup_by_name = {}
    result_by_team = {}
    if last_week is not None:
        spreads = NflSurvivorSpread.query.filter_by(
            season_id=season.id, week=last_week
        ).all()
        for spread in spreads:
            matchup_by_name[spread.home_team] = spread.road_team
            matchup_by_name[spread.road_team] = spread.home_team
        results = NflSurvivorWeeklyResult.query.filter_by(
            season_id=season.id, week=last_week
        ).all()
        result_by_team = {row.team: row.result for row in results}

    wrong_counts = {}
    for participant_id, entry_picks in picks_by_entry.items():
        wrong_counts[participant_id] = sum(
            1 for pick in entry_picks if pick.is_correct is False
        )

    alive_count = sum(
        1 for participant in participants if wrong_counts.get(participant.id, 0) < 2
    )

    last_week_pick_counts = []
    last_week_results_pending = False
    if last_week is not None:
        last_week_picks = [pick for pick in picks if pick.week == last_week]
        last_week_results_pending = any(
            pick.is_correct is None for pick in last_week_picks
        )
        if last_week_revealed:
            counter = Counter()
            for pick in last_week_picks:
                counter[team_lookup.get(pick.team, pick.team)] += 1
            last_week_pick_counts = counter.most_common()

    return {
        "current_week": current_week,
        "last_week": last_week,
        "last_week_revealed": last_week_revealed,
        "participants": participants,
        "picks_by_entry": picks_by_entry,
        "wrong_counts": wrong_counts,
        "team_lookup": team_lookup,
        "matchup_by_name": matchup_by_name,
        "result_by_team": result_by_team,
        "alive_count": alive_count,
        "total_count": len(participants),
        "last_week_pick_counts": last_week_pick_counts,
        "last_week_results_pending": last_week_results_pending,
        "pick_week_open": current_week <= season.max_weeks,
    }


def build_user_payload(season, user, data):
    """Return email payload for one user, or None if there is nothing to send."""
    user_entries = [
        entry for entry in data["participants"] if entry.user_id == user.id
    ]
    if not user_entries:
        return None

    last_week = data["last_week"]
    current_week = data["current_week"]
    sections = []
    eliminated_entry_ids = []
    needs_any_pick = False

    for entry in user_entries:
        losses = data["wrong_counts"].get(entry.id, 0)
        kind = classify_entry(losses, entry.elimination_email_sent_at)
        if kind == "skip":
            continue

        entry_picks = data["picks_by_entry"].get(entry.id, [])
        last_pick = next((p for p in entry_picks if p.week == last_week), None)
        this_pick = next((p for p in entry_picks if p.week == current_week), None)
        last_team, last_outcome = _last_week_pick_line(
            last_pick,
            data["team_lookup"],
            data["matchup_by_name"],
            data["result_by_team"],
        )
        this_team = (
            data["team_lookup"].get(this_pick.team, this_pick.team)
            if this_pick
            else None
        )

        if kind == "new_out":
            sections.append(
                {
                    "display_name": entry.display_name,
                    "status": "eliminated",
                    "losses": losses,
                    "last_week_team": last_team,
                    "last_week_outcome": last_outcome,
                    "this_week_team": None,
                    "needs_pick": False,
                }
            )
            eliminated_entry_ids.append(entry.id)
            continue

        needs_pick = data["pick_week_open"] and this_pick is None
        if needs_pick:
            needs_any_pick = True
        sections.append(
            {
                "display_name": entry.display_name,
                "status": "alive",
                "losses": losses,
                "last_week_team": last_team,
                "last_week_outcome": last_outcome,
                "this_week_team": this_team,
                "needs_pick": needs_pick,
            }
        )

    if not sections:
        return None

    return {
        "season_name": season.name,
        "current_week": current_week,
        "last_week": last_week,
        "pick_week_open": data["pick_week_open"],
        "alive_count": data["alive_count"],
        "total_count": data["total_count"],
        "last_week_pick_counts": data["last_week_pick_counts"],
        "last_week_results_pending": data["last_week_results_pending"],
        "entries": sections,
        "eliminated_entry_ids": eliminated_entry_ids,
        "needs_any_pick": needs_any_pick,
    }


def send_user_reminder(season, user, data, *, update_tracking=True, pref=None):
    """
    Send one reminder if the user has content. Returns a status string.
    """
    from app.projects.nfl_survivor.email import send_reminder_email

    payload = build_user_payload(season, user, data)
    if payload is None:
        return "skipped_empty"
    if not user.email_verified:
        return "skipped_unverified"

    send_reminder_email(user, payload)

    if update_tracking:
        now = datetime.utcnow()
        if pref is None:
            pref = NflSurvivorEmailPref.query.filter_by(user_id=user.id).first()
        if pref is not None:
            pref.last_sent_at = now
        id_set = set(payload["eliminated_entry_ids"])
        for entry in data["participants"]:
            if entry.id in id_set:
                entry.elimination_email_sent_at = now
        log_nfl_survivor(
            "Email Reminders",
            f"Sent reminder email to {user.email} ({season.name})",
            actor_id=None,
        )
        db.session.commit()
    return "sent"


def run_reminder_send(*, when=None, user_id=None, force=False, dry_run=False):
    """
    Send due reminder emails for the active season.

    force: ignore weekday and last_sent_at (requires user_id).
    dry_run: log who would be emailed, do not send.
    """
    from app.projects.nfl_survivor.utils import get_active_season

    season = get_active_season()
    if not season:
        return {"error": "No active NFL Survivor season."}

    now_eastern = _now_eastern(when)
    today_weekday = now_eastern.weekday()
    data = load_reminder_season_data(season)

    query = NflSurvivorEmailPref.query.options(
        joinedload(NflSurvivorEmailPref.user)
    )
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    else:
        query = query.filter(NflSurvivorEmailPref.reminder_weekday == today_weekday)

    prefs = query.all()

    if force and user_id is not None and not prefs:
        user = User.query.filter_by(id=user_id).first()
        if not user:
            return {"error": f"User {user_id} not found."}
        prefs = [
            NflSurvivorEmailPref(
                user_id=user.id, reminder_weekday=None, user=user
            )
        ]

    counts = {
        "candidates": 0,
        "sent": 0,
        "failed": 0,
        "skipped_day": 0,
        "skipped_already": 0,
        "skipped_empty": 0,
        "skipped_unverified": 0,
        "dry_run": 0,
    }

    for pref in prefs:
        user = pref.user
        if user is None:
            continue
        counts["candidates"] += 1
        if not should_send_pref(
            pref.reminder_weekday,
            today_weekday,
            pref.last_sent_at,
            now_eastern,
            force=force,
        ):
            if already_sent_today(pref.last_sent_at, now_eastern) and (
                force or pref.reminder_weekday == today_weekday
            ):
                counts["skipped_already"] += 1
            else:
                counts["skipped_day"] += 1
            continue

        if dry_run:
            payload = build_user_payload(season, user, data)
            if payload is None:
                counts["skipped_empty"] += 1
            elif not user.email_verified:
                counts["skipped_unverified"] += 1
            else:
                counts["dry_run"] += 1
            continue

        try:
            status = send_user_reminder(
                season, user, data, update_tracking=not force, pref=pref
            )
        except Exception as exc:
            logger.exception("NFL Survivor reminder failed for user_id=%s", user.id)
            log_nfl_survivor(
                "Email Reminders",
                f"Failed reminder email to {user.email} ({season.name}): {exc}",
                actor_id=None,
            )
            db.session.commit()
            counts["failed"] += 1
            continue

        if status == "sent":
            counts["sent"] += 1
        elif status == "skipped_empty":
            counts["skipped_empty"] += 1
        elif status == "skipped_unverified":
            counts["skipped_unverified"] += 1

    return counts
