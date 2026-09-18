"""NFL Survivor helpers: teams, week math, display names."""

import json
from datetime import datetime, time, timedelta
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

# Python weekday(): Mon=0 … Sun=6. None (no emails) is NULL, never 0.
REMINDER_WEEKDAYS = (2, 3, 4, 5, 6)
REMINDER_WEEKDAY_LABELS = {
    2: "Wednesday morning",
    3: "Thursday morning",
    4: "Friday morning",
    5: "Saturday morning",
    6: "Sunday morning",
}
REMINDER_WEEKDAY_SHORT_LABELS = {
    2: "Wed morning",
    3: "Thu morning",
    4: "Fri morning",
    5: "Sat morning",
    6: "Sun morning",
}


def reminder_weekday_choices():
    """Select options: empty string = none, then Wed–Sun."""
    return [("", "None")] + [
        (str(day), REMINDER_WEEKDAY_SHORT_LABELS[day]) for day in REMINDER_WEEKDAYS
    ]


def parse_reminder_weekday(value):
    """Return weekday int or None for 'none'. Raise ValueError if invalid."""
    if value in (None, ""):
        return None
    try:
        day = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid reminder weekday") from exc
    if day not in REMINDER_WEEKDAYS:
        raise ValueError("invalid reminder weekday")
    return day


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


def get_week_date_range(season, week):
    """Tue–Mon calendar dates (US/Eastern) covered by this pick week."""
    lock = _to_eastern(get_week_pick_lock_time(season, week))
    tuesday = (lock - timedelta(days=7)).date()
    monday = (lock - timedelta(days=1)).date()
    return tuesday, monday


def format_week_choice_label(season, week):
    """Dropdown label: 'Week 3 · Tue Sep 22 – Mon Sep 28'."""
    tuesday, monday = get_week_date_range(season, week)
    return (
        f"Week {week} · {tuesday.strftime('%a %b %-d')} – "
        f"{monday.strftime('%a %b %-d')}"
    )


def get_week_picks_reveal_time(season, week):
    """Monday 8:30pm ET before the Tuesday that ends this pick week."""
    tuesday = get_week_pick_lock_time(season, week)
    eastern_tue = _to_eastern(tuesday)
    monday_date = eastern_tue.date() - timedelta(days=eastern_tue.weekday())
    return EASTERN.localize(datetime.combine(monday_date, time(20, 30)))


def is_week_picks_revealed(season, week, when=None):
    if when is None:
        when = datetime.now(EASTERN)
    elif when.tzinfo is None:
        when = EASTERN.localize(when)
    else:
        when = when.astimezone(EASTERN)
    return when >= get_week_picks_reveal_time(season, week)


def is_week_pickable(season, week):
    return datetime.now(EASTERN) < get_week_pick_lock_time(season, week)


def is_join_open(season):
    # Join closes at the first Tuesday boundary only.
    return is_week_pickable(season, 1)


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
    return format_kickoff_label(kickoff)


def format_kickoff_label(kickoff):
    """Human-readable kickoff in Eastern, or empty string."""
    aware = _kickoff_utc(kickoff)
    if aware is None:
        return ""
    return aware.astimezone(EASTERN).strftime("%a %b %-d, %-I:%M %p ET")


def _kickoff_utc(kickoff):
    if kickoff is None:
        return None
    if kickoff.tzinfo is None:
        return UTC.localize(kickoff)
    return kickoff.astimezone(UTC)


def select_last_game_rows(game_rows):
    """
    Team rows for the latest kickoff's game.

    If two games share that kickoff, the lower ESPN event id wins. Returns
    (rows, kickoff) or ([], None).
    """
    dated = []
    for row in game_rows:
        kickoff = _kickoff_utc(getattr(row, "kickoff", None))
        if kickoff is None:
            continue
        dated.append((kickoff, row))
    if not dated:
        return [], None

    last_kickoff = max(kickoff for kickoff, _ in dated)
    at_last = [row for kickoff, row in dated if kickoff == last_kickoff]
    groups = {}
    ungrouped = []
    for row in at_last:
        event_id = getattr(row, "espn_event_id", None) or ""
        if event_id:
            groups.setdefault(event_id, []).append(row)
        else:
            ungrouped.append(row)
    if groups:
        event_id = sorted(groups.keys())[0]
        return groups[event_id], last_kickoff
    return ungrouped, last_kickoff


def resolve_last_game_sides(game_rows, spread_rows, id_to_name):
    """
    Favorite and underdog of the week's last game.

    Pick'em (equal spreads) treats the home team as the favorite.
    """
    rows, kickoff = select_last_game_rows(game_rows)
    if not rows or kickoff is None:
        return {"found": False, "reason": "no_schedule"}

    team_names = []
    for row in rows:
        team_id = str(row.team_id)
        team_names.append(id_to_name.get(team_id, team_id))
    unique_names = sorted(set(team_names))
    if len(unique_names) != 2:
        return {
            "found": False,
            "reason": "incomplete_game",
            "kickoff": kickoff,
            "kickoff_label": format_kickoff_label(kickoff),
            "team_names": unique_names,
        }

    name_set = set(unique_names)
    matched = None
    for spread in spread_rows:
        if {spread.home_team, spread.road_team} == name_set:
            matched = spread
            break
    if matched is None:
        return {
            "found": False,
            "reason": "no_spread",
            "kickoff": kickoff,
            "kickoff_label": format_kickoff_label(kickoff),
            "team_names": unique_names,
        }

    if matched.home_team_spread <= matched.road_team_spread:
        favorite = matched.home_team
        underdog = matched.road_team
        favorite_spread = matched.home_team_spread
        underdog_spread = matched.road_team_spread
    else:
        favorite = matched.road_team
        underdog = matched.home_team
        favorite_spread = matched.road_team_spread
        underdog_spread = matched.home_team_spread

    return {
        "found": True,
        "reason": None,
        "kickoff": kickoff,
        "kickoff_label": format_kickoff_label(kickoff),
        "home_team": matched.home_team,
        "road_team": matched.road_team,
        "favorite": favorite,
        "underdog": underdog,
        "favorite_spread": favorite_spread,
        "underdog_spread": underdog_spread,
        "favorite_spread_display": format_team_spread(favorite_spread),
        "underdog_spread_display": format_team_spread(underdog_spread),
    }


def last_game_auto_pick_info(season, week):
    """Load schedule + spreads and resolve the week's last-game auto-pick sides."""
    games = NflSurvivorGame.query.filter_by(season_id=season.id, week=week).all()
    spreads = NflSurvivorSpread.query.filter_by(
        season_id=season.id, week=week
    ).all()
    return resolve_last_game_sides(games, spreads, load_nfl_teams_as_dict())


def choose_last_game_auto_pick(used_team_names, last_game):
    """
    Last-game favorite if unused, else underdog, else nobody.

    Returns (team_name or None, reason). Kickoff having passed does not skip.
    """
    if not last_game or not last_game.get("found"):
        return None, (last_game or {}).get("reason") or "no_last_game"
    used = set(used_team_names)
    favorite = last_game["favorite"]
    underdog = last_game["underdog"]
    if favorite not in used:
        return favorite, "favorite"
    if underdog not in used:
        return underdog, "underdog"
    return None, "both_used"


AUTO_PICK_REASON_LABELS = {
    "favorite": "Last-game favorite",
    "underdog": "Last-game underdog",
    "already_picked": "Already picked",
    "eliminated": "Eliminated",
    "both_used": "Already used both last-game teams",
    "no_schedule": "No last game on the schedule",
    "incomplete_game": "Last game is incomplete on the schedule",
    "no_spread": "No spread for the last game",
    "no_last_game": "No last game",
}


def auto_pick_reason_label(reason):
    return AUTO_PICK_REASON_LABELS.get(reason, reason or "")


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

