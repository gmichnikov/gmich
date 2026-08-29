"""NFL Survivor helpers: teams, week math, display names."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytz
from flask import session

from app.projects.nfl_survivor.models import (
    NflSurvivorGame,
    NflSurvivorParticipant,
    NflSurvivorPick,
    NflSurvivorSeason,
    NflSurvivorSpread,
    NflSurvivorWeeklyResult,
)

EASTERN = pytz.timezone("US/Eastern")
UTC = pytz.UTC
DATA_DIR = Path(__file__).resolve().parent / "data"
ACTIVE_ENTRY_SESSION_KEY = "nfl_survivor_active_entry_id"
MAX_ENTRY_NAME_LENGTH = 100


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


def normalize_entry_name(name):
    return (name or "").strip()


def entry_name_taken(season_id, display_name, exclude_participant_id=None):
    display_name = normalize_entry_name(display_name)
    if not display_name:
        return True
    query = NflSurvivorParticipant.query.filter_by(
        season_id=season_id, display_name=display_name
    )
    if exclude_participant_id is not None:
        query = query.filter(NflSurvivorParticipant.id != exclude_participant_id)
    return query.first() is not None


def default_entry_name_for_user(season, user):
    base = (user.full_name or user.email.split("@")[0]).strip()
    entry_count = NflSurvivorParticipant.query.filter_by(
        season_id=season.id, user_id=user.id
    ).count()
    if entry_count == 0:
        candidate = base
    else:
        candidate = f"{base} #{entry_count + 1}"

    if not entry_name_taken(season.id, candidate):
        return candidate

    suffix = entry_count + 2
    while entry_name_taken(season.id, f"{base} #{suffix}"):
        suffix += 1
    return f"{base} #{suffix}"


def get_user_entries(season, user_id):
    if not season:
        return []
    return (
        NflSurvivorParticipant.query.filter_by(season_id=season.id, user_id=user_id)
        .order_by(NflSurvivorParticipant.joined_at.asc())
        .all()
    )


def resolve_active_entry(season, user_id):
    entries = get_user_entries(season, user_id)
    if not entries:
        return None

    stored_id = session.get(ACTIVE_ENTRY_SESSION_KEY)
    if stored_id is not None:
        for entry in entries:
            if entry.id == stored_id:
                return entry

    return entries[0]


def set_active_entry(participant_id):
    session[ACTIVE_ENTRY_SESSION_KEY] = participant_id


def clear_active_entry():
    session.pop(ACTIVE_ENTRY_SESSION_KEY, None)


def participant_wrong_picks_count(participant):
    return NflSurvivorPick.query.filter_by(
        participant_id=participant.id, is_correct=False
    ).count()


def participant_correct_picks_count(participant):
    return NflSurvivorPick.query.filter_by(
        participant_id=participant.id, is_correct=True
    ).count()


def participant_is_eliminated(participant):
    return participant_wrong_picks_count(participant) >= 2


def entry_log_description(entry):
    owner = entry.user.full_name or entry.user.email
    return f'entry "{entry.display_name}" ({owner})'


def validate_entry_name(season_id, display_name, exclude_participant_id=None):
    display_name = normalize_entry_name(display_name)
    if not display_name:
        return None, "Entry name is required."
    if len(display_name) > MAX_ENTRY_NAME_LENGTH:
        return None, f"Entry name must be {MAX_ENTRY_NAME_LENGTH} characters or fewer."
    if entry_name_taken(season_id, display_name, exclude_participant_id):
        return None, "That entry name is already taken."
    return display_name, None


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


def get_team_kickoff(season_id, week, team_id):
    """Return kickoff as UTC-aware datetime, or None if unknown."""
    game = NflSurvivorGame.query.filter_by(
        season_id=season_id, week=week, team_id=str(team_id)
    ).first()
    if not game or not game.kickoff:
        return None
    kickoff = game.kickoff
    if kickoff.tzinfo is None:
        return UTC.localize(kickoff)
    return kickoff.astimezone(UTC)


def is_team_kickoff_locked(season, week, team_id):
    """True if this team's game for the week has started (or no schedule = unlocked)."""
    kickoff = get_team_kickoff(season.id, week, team_id)
    if kickoff is None:
        return False
    return datetime.now(UTC) >= kickoff


def teams_available_for_week(season, week, picked_team_ids):
    """
    Team (id, name) pairs pickable for `week`: not already used and kickoff not passed.
    """
    pairs = []
    for team_id, team_name in load_nfl_teams_as_pairs():
        if team_id in picked_team_ids:
            continue
        if is_team_kickoff_locked(season, week, team_id):
            continue
        pairs.append((team_id, team_name))
    return pairs


def format_kickoff_et(season_id, week, team_id):
    """Human-readable kickoff in Eastern, or empty string."""
    kickoff = get_team_kickoff(season_id, week, team_id)
    if not kickoff:
        return ""
    return kickoff.astimezone(EASTERN).strftime("%a %b %-d, %-I:%M %p ET")


def format_team_spread(spread_value):
    """Format spread for display, e.g. -7 or +3."""
    if spread_value is None:
        return None
    if spread_value == int(spread_value):
        spread_value = int(spread_value)
    if spread_value <= 0:
        return str(spread_value)
    return f"+{spread_value}"


def format_team_pick_label(team_name, opponent=None, spread_display=None):
    """Single-line dropdown label with optional spread and opponent."""
    if opponent and spread_display is not None:
        return f"{team_name} ({spread_display} vs {opponent})"
    return team_name


def build_team_pick_options(season, week, available_team_pairs):
    """
    Enrich pickable teams with opponent and spread when both are known.
    `available_team_pairs` is a list of (team_id, team_name).
    """
    spreads = NflSurvivorSpread.query.filter_by(
        season_id=season.id, week=week
    ).all()
    matchup_by_name = {}
    for spread in spreads:
        matchup_by_name[spread.home_team] = {
            "opponent": spread.road_team,
            "spread": spread.home_team_spread,
        }
        matchup_by_name[spread.road_team] = {
            "opponent": spread.home_team,
            "spread": spread.road_team_spread,
        }

    options = []
    for team_id, team_name in available_team_pairs:
        matchup = matchup_by_name.get(team_name, {})
        opponent = matchup.get("opponent")
        spread_display = format_team_spread(matchup.get("spread"))
        options.append(
            {
                "team_id": team_id,
                "team_name": team_name,
                "label": format_team_pick_label(
                    team_name,
                    opponent=opponent,
                    spread_display=spread_display,
                ),
            }
        )
    return options


def team_pick_choices(season, week, available_team_pairs):
    """SelectField choices: (team_id, enriched label)."""
    return [
        (option["team_id"], option["label"])
        for option in build_team_pick_options(season, week, available_team_pairs)
    ]


def format_pick_outcome(result, opponent):
    """Human-readable result vs opponent, or None if not yet known."""
    if not result:
        return None
    if result == "did not play":
        return "Did not play"
    if not opponent:
        return result.capitalize()
    if result == "win":
        return f"Beat {opponent}"
    if result == "lose":
        return f"Lost to {opponent}"
    if result == "tie":
        return f"Tied {opponent}"
    return result.replace("_", " ").capitalize()


def build_entry_pick_history(season, participant):
    """
    Per-week pick summary for one entry: team, spread, opponent, and result.
    """
    team_lookup = load_nfl_teams_as_dict()
    picks = (
        NflSurvivorPick.query.filter_by(participant_id=participant.id)
        .order_by(NflSurvivorPick.week.asc())
        .all()
    )
    if not picks:
        return []

    weeks = [pick.week for pick in picks]
    spreads = NflSurvivorSpread.query.filter_by(season_id=season.id).filter(
        NflSurvivorSpread.week.in_(weeks)
    ).all()
    matchup_by_week_name = {}
    for spread in spreads:
        week_map = matchup_by_week_name.setdefault(spread.week, {})
        week_map[spread.home_team] = {
            "opponent": spread.road_team,
            "spread": spread.home_team_spread,
        }
        week_map[spread.road_team] = {
            "opponent": spread.home_team,
            "spread": spread.road_team_spread,
        }

    weekly_results = NflSurvivorWeeklyResult.query.filter_by(
        season_id=season.id
    ).filter(NflSurvivorWeeklyResult.week.in_(weeks)).all()
    result_by_week_team = {
        (result.week, result.team): result.result for result in weekly_results
    }

    history = []
    for pick in picks:
        team_name = team_lookup.get(pick.team, pick.team)
        matchup = matchup_by_week_name.get(pick.week, {}).get(team_name, {})
        opponent = matchup.get("opponent")
        spread_display = format_team_spread(matchup.get("spread"))
        result = result_by_week_team.get((pick.week, pick.team))
        history.append(
            {
                "week": pick.week,
                "team_name": team_name,
                "opponent": opponent,
                "spread_display": spread_display,
                "pick_label": format_team_pick_label(
                    team_name,
                    opponent=opponent,
                    spread_display=spread_display,
                ),
                "result": result,
                "outcome": format_pick_outcome(result, opponent),
                "is_correct": pick.is_correct,
            }
        )
    return history

