"""NFL Survivor helpers: teams, week math, display names."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytz

from app.projects.nfl_survivor.models import NflSurvivorSeason, NflSurvivorWeeklyResult

EASTERN = pytz.timezone("US/Eastern")
UTC = pytz.UTC
DATA_DIR = Path(__file__).resolve().parent / "data"


def load_nfl_teams():
    with open(DATA_DIR / "nfl_teams.json", encoding="utf-8") as json_file:
        return json.load(json_file)


def load_nfl_teams_as_pairs():
    return [(team["id"], team["name"]) for team in load_nfl_teams()]


def load_nfl_teams_as_dict():
    return {team["id"]: team["name"] for team in load_nfl_teams()}


def get_active_season():
    return NflSurvivorSeason.query.filter_by(is_active=True).first()


def _to_eastern(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return EASTERN.localize(dt)
    return dt.astimezone(EASTERN)


def _week_2_start_utc(season):
    """week_2_start stored as UTC-aware; normalize for comparisons."""
    anchor = season.week_2_start
    if anchor.tzinfo is None:
        return UTC.localize(anchor)
    return anchor.astimezone(UTC)


def get_current_pick_week(season):
    """Week 1 until week_2_start, then +1 each 7 days."""
    now = datetime.now(EASTERN)
    week_2_start = _to_eastern(season.week_2_start)
    if now < week_2_start:
        return 1
    return 2 + ((now - week_2_start).days // 7)


def get_week_pick_lock_time(season, week):
    """When picks for `week` lock (same Tuesday cadence as week rollover)."""
    anchor = _to_eastern(season.week_2_start)
    if week < 1:
        raise ValueError("week must be >= 1")
    return anchor + timedelta(days=(week - 1) * 7)


def is_week_pickable(season, week):
    return datetime.now(EASTERN) < get_week_pick_lock_time(season, week)


def is_join_open(season):
    # Join closes at the first Tuesday boundary only.
    return is_week_pickable(season, 1)


def get_odds_fetch_window(season, current_week):
    """
    Return (window_start, window_end) in US/Eastern for the current pick week.
    Week 1 spans the 7 days before the first Tuesday; later weeks are Tue–Tue.
    """
    anchor = _to_eastern(season.week_2_start)
    if current_week == 1:
        window_start = anchor - timedelta(days=7)
        window_end = anchor
    else:
        window_start = anchor + timedelta(days=(current_week - 2) * 7)
        window_end = window_start + timedelta(days=7)
    return window_start, window_end


def calculate_game_week(season, game_time_utc):
    if game_time_utc.tzinfo is None:
        game_time_utc = UTC.localize(game_time_utc)
    anchor = _week_2_start_utc(season)
    if game_time_utc < anchor:
        return 1
    delta_days = (game_time_utc - anchor).days
    return 2 + (delta_days // 7)


def is_pick_correct(season_id, user_pick, week):
    weekly_result = NflSurvivorWeeklyResult.query.filter_by(
        season_id=season_id, week=week, team=user_pick
    ).first()
    if weekly_result:
        return weekly_result.result in ("win", "tie")
    return False


def build_display_names(users):
    """Map user id -> label; disambiguate duplicate full_names."""
    counts = {}
    for user in users:
        label = user.full_name or user.email
        counts[label] = counts.get(label, 0) + 1

    labels = {}
    for user in users:
        label = user.full_name or user.email
        if counts[label] > 1:
            labels[user.id] = f"{label} ({user.email.split('@')[0]})"
        else:
            labels[user.id] = label
    return labels


def map_team_names_to_ids():
    return {team["name"]: team["id"] for team in load_nfl_teams()}


def parse_eastern_datetime(value):
    """Parse 'YYYY-MM-DD HH:MM' as US/Eastern, return UTC-aware datetime."""
    naive = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M")
    return EASTERN.localize(naive).astimezone(UTC)


# Tuesday and Thursday (US/Eastern) — matches Heroku daily scheduler cadence.
SCHEDULED_SPREADS_WEEKDAYS = (1, 3)  # Mon=0 … Tue=1 … Thu=3


def is_scheduled_spreads_day(when=None):
    """True if today (US/Eastern) is a day we auto-fetch spreads."""
    if when is None:
        when = datetime.now(EASTERN)
    elif when.tzinfo is None:
        when = EASTERN.localize(when)
    else:
        when = when.astimezone(EASTERN)
    return when.weekday() in SCHEDULED_SPREADS_WEEKDAYS


