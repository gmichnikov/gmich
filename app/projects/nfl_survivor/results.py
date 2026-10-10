"""NFL Survivor game results fetching, pick evaluation, and automation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import requests
from flask_login import current_user

from app import db
from app.projects.nfl_survivor.log import log_nfl_survivor
from app.projects.nfl_survivor.models import NflSurvivorPick, NflSurvivorWeeklyResult
from app.projects.nfl_survivor.utils import (
    EASTERN,
    _to_eastern,
    get_active_season,
    is_pick_correct,
    map_team_names_to_ids,
)

logger = logging.getLogger(__name__)

TUESDAY_WEEKDAY = 1


def _now_eastern(when=None):
    if when is None:
        return datetime.now(EASTERN)
    if when.tzinfo is None:
        return EASTERN.localize(when)
    return when.astimezone(EASTERN)


def is_tuesday(when=None):
    """True if `when` (US/Eastern) is Tuesday."""
    return _now_eastern(when).weekday() == TUESDAY_WEEKDAY


def get_recently_finished_week(season, when=None):
    """
    Return the integer week number for the NFL week that just finished on Monday night.
    Returns None if the season hasn't completed Week 1 yet or is past max_weeks.
    """
    now = _now_eastern(when)
    today = now.date()

    # NFL weeks run Tuesday through Monday.
    # On Tuesday (weekday 1), yesterday was Monday (the final day of the completed week).
    # If run on any other day (e.g. forced), look back to the most recently completed Monday.
    if today.weekday() == 0:
        # On Monday, the current week's Monday night game has not yet finished.
        # The last completed week is the one from the previous Monday (7 days ago).
        days_since_monday = 7
    else:
        days_since_monday = (today.weekday() - 0) % 7

    most_recent_monday = today - timedelta(days=days_since_monday)
    tuesday_after_mnf = most_recent_monday + timedelta(days=1)

    anchor_date = _to_eastern(season.week_2_start).date()
    days_diff = (tuesday_after_mnf - anchor_date).days
    week = 1 + (days_diff // 7)

    if week < 1 or week > season.max_weeks:
        return None
    return week


def fetch_results_for_week(season, week):
    """
    Query ESPN scoreboard API for completed games and byes for `week`.
    Returns a dict mapping team display name to 'win', 'lose', 'tie', or 'did not play'.
    """
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
        f"?dates={season.espn_season_year}&seasontype=2&week={week}"
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    teams_on_bye = {
        team["displayName"]: "did not play"
        for team in data.get("week", {}).get("teamsOnBye", [])
    }
    game_results = {}
    for event in data.get("events", []):
        for competition in event.get("competitions", []):
            status_type = competition.get("status", {}).get("type", {})
            # Only record results for completed games
            if not status_type.get("completed", False):
                continue

            competitors = competition.get("competitors", [])
            # Check for a tie (neither competitor marked as winner in a completed game)
            is_tie = not any(c.get("winner") is True for c in competitors)

            for competitor in competitors:
                team_name = competitor.get("team", {}).get("displayName")
                if not team_name:
                    continue
                if is_tie:
                    result = "tie"
                else:
                    result = "win" if competitor.get("winner") is True else "lose"
                game_results[team_name] = result
    return {**teams_on_bye, **game_results}


def update_weekly_results(season, week, results, *, actor_name=None, actor_id=None, source="cron"):
    """
    Save weekly team results to NflSurvivorWeeklyResult and update correctness
    on all NflSurvivorPick rows for `week`.
    """
    team_name_to_id = map_team_names_to_ids()
    updated_teams_count = 0
    for team_name, result in results.items():
        team_id = team_name_to_id.get(team_name)
        if not team_id:
            continue
        weekly_result = NflSurvivorWeeklyResult.query.filter_by(
            season_id=season.id, week=week, team=team_id
        ).first()
        if weekly_result:
            weekly_result.result = result
        else:
            db.session.add(
                NflSurvivorWeeklyResult(
                    season_id=season.id,
                    week=week,
                    team=team_id,
                    result=result,
                )
            )
        updated_teams_count += 1

    if actor_name:
        actor_label = actor_name
    elif current_user and getattr(current_user, "is_authenticated", False):
        actor_label = getattr(current_user, "full_name", "Admin")
        if actor_id is None:
            actor_id = getattr(current_user, "id", None)
    else:
        actor_label = "Cron" if source == "cron" else "Manual"

    log_nfl_survivor(
        "Auto Update",
        f"{actor_label} auto-updated results for week {week} ({season.name}): {updated_teams_count} teams",
        actor_id=actor_id,
    )
    db.session.commit()

    all_picks = NflSurvivorPick.query.filter_by(season_id=season.id, week=week).all()
    updated_picks_count = 0
    for pick in all_picks:
        pick.is_correct = is_pick_correct(season.id, pick.team, week)
        updated_picks_count += 1
    db.session.commit()

    return {
        "teams_updated": updated_teams_count,
        "picks_updated": updated_picks_count,
    }


def run_auto_update_results(*, force=False, now_eastern=None):
    """
    Execute automated results update for the week that just finished.
    Skips if today is not Tuesday (unless force=True), or if no active season.
    """
    now = _now_eastern(now_eastern)

    if not force and not is_tuesday(now):
        return {
            "skipped_day": True,
            "message": "Skipped: update-results only runs on Tuesday (US/Eastern).",
        }

    season = get_active_season()
    if not season:
        return {"error": "No active NFL Survivor season."}

    week = get_recently_finished_week(season, when=now)
    if week is None:
        return {
            "skipped_out_of_bounds": True,
            "message": f"Skipped: no completed regular season week to update for {season.name}.",
        }

    try:
        results = fetch_results_for_week(season, week)
        counts = update_weekly_results(season, week, results, source="cron")
    except Exception as exc:
        log_nfl_survivor(
            "Auto Update",
            f"Cron auto-update results failed for week {week} ({season.name}): {exc}",
            actor_id=None,
        )
        db.session.commit()
        logger.exception("Failed to update results for week %s: %s", week, exc)
        return {"error": str(exc), "week": week}

    return {
        "success": True,
        "season_name": season.name,
        "week": week,
        "teams_updated": counts["teams_updated"],
        "picks_updated": counts["picks_updated"],
        "message": (
            f"Updated week {week} results ({season.name}): "
            f"{counts['teams_updated']} teams, {counts['picks_updated']} picks evaluated."
        ),
    }
