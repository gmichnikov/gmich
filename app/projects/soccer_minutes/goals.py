"""Goals and derived score. Separate from the field event log."""

from datetime import datetime

from app.projects.soccer_minutes.clock import format_ms
from app.projects.soccer_minutes.field_state import player_chip_label
from app.projects.soccer_minutes.live_state import event_assignments
from app.projects.soccer_minutes.models import ScmGoal

SIDE_US = "us"
SIDE_THEM = "them"
SIDES = (SIDE_US, SIDE_THEM)
LIVE_CLOCK_SLACK_MS = 2000


def ordered_goals(game, goals=None):
    if goals is not None:
        return list(goals)
    query = getattr(game, "goals", None)
    if query is None:
        return []
    if hasattr(query, "order_by"):
        return query.order_by(ScmGoal.period, ScmGoal.at_ms, ScmGoal.id).all()
    return list(query)


def score_from_goals(goals):
    us = 0
    them = 0
    for goal in goals:
        if getattr(goal, "side", None) == SIDE_US:
            us += 1
        elif getattr(goal, "side", None) == SIDE_THEM:
            them += 1
    return {
        "us": us,
        "them": them,
        "displayed": f"{us}–{them}",
        "has_goals": (us + them) > 0,
    }


def scores_by_game_id(game_ids):
    result = {}
    for game_id in game_ids:
        result[game_id] = score_from_goals([])
    if not game_ids:
        return result
    goals = ScmGoal.query.filter(ScmGoal.game_id.in_(list(game_ids))).all()
    by_game = {game_id: [] for game_id in game_ids}
    for goal in goals:
        by_game.setdefault(goal.game_id, []).append(goal)
    return {game_id: score_from_goals(rows) for game_id, rows in by_game.items()}


def started_periods(events):
    return sorted(
        {int(event.period) for event in events if event.type == "period_start"}
    )


def period_goal_max_ms(
    events, period, displayed_ms=None, current_period=None, phase=None
):
    """Latest legal stamp for a goal in this period, or None if it has not started."""
    started = False
    end_ms = None
    latest = 0
    for event in events:
        if int(event.period) != int(period):
            continue
        latest = max(latest, int(event.at_ms or 0))
        if event.type == "period_start":
            started = True
        elif event.type == "period_end":
            end_ms = int(event.at_ms or 0)
    if not started:
        return None
    if end_ms is not None:
        return end_ms
    if (
        phase == "live"
        and int(current_period or 0) == int(period)
        and displayed_ms is not None
    ):
        return max(0, int(displayed_ms))
    return latest


def assignments_at_ms(events, formation, period, at_ms):
    field = {}
    stamp = int(at_ms or 0)
    for event in events:
        if int(event.period) != int(period):
            continue
        if int(event.at_ms or 0) > stamp:
            break
        if event.type in ("period_start", "field_set"):
            field = event_assignments(event, formation)
    return field


def player_on_field_at(events, formation, period, at_ms, player_id):
    if not player_id:
        return False
    try:
        target = int(player_id)
    except (TypeError, ValueError):
        return False
    field = assignments_at_ms(events, formation, period, at_ms)
    for value in field.values():
        try:
            if int(value) == target:
                return True
        except (TypeError, ValueError):
            continue
    return False


def clear_player_from_goal(goal, player_id):
    try:
        target = int(player_id)
    except (TypeError, ValueError):
        return False
    changed = False
    if goal.scorer_id is not None and int(goal.scorer_id) == target:
        goal.scorer_id = None
        changed = True
    if goal.assist_id is not None and int(goal.assist_id) == target:
        goal.assist_id = None
        changed = True
    return changed


def goal_player_options(players, present_ids, live_assignments=None):
    on_ids = set()
    if live_assignments:
        for value in live_assignments.values():
            try:
                on_ids.add(int(value))
            except (TypeError, ValueError):
                continue
    options = []
    for player in players:
        if player.id not in present_ids:
            continue
        options.append(
            {
                "id": player.id,
                "label": player_chip_label(player),
                "on_field": player.id in on_ids,
            }
        )
    options.sort(key=lambda row: (not row["on_field"], row["label"].lower()))
    return options


def _parse_player_id(raw, required, label):
    if raw is None or raw == "" or raw == "none":
        if required:
            return None, f"{label} is required."
        return None, None
    try:
        return int(raw), None
    except (TypeError, ValueError):
        return None, f"{label} is required."


def validate_goal(
    *,
    side,
    period,
    at_ms,
    scorer_id,
    assist_id,
    events,
    present_ids,
    displayed_ms=None,
    current_period=None,
    phase=None,
    require_scorer=True,
):
    if side not in SIDES:
        return "Choose We scored or They scored.", None
    try:
        period = int(period)
    except (TypeError, ValueError):
        return "Pick a period.", None
    if period < 1:
        return "Pick a period.", None

    max_ms = period_goal_max_ms(
        events,
        period,
        displayed_ms=displayed_ms,
        current_period=current_period,
        phase=phase,
    )
    if max_ms is None:
        return "That period has not started.", None
    try:
        at_ms = int(at_ms)
    except (TypeError, ValueError):
        return "Enter a time like 8:00.", None
    if at_ms < 0:
        return "Time cannot be negative.", None
    if at_ms > max_ms:
        # Live client clocks are often ~1s ahead of the server; clamp that.
        live_now = (
            phase == "live" and int(current_period or 0) == int(period)
        )
        if live_now and at_ms <= max_ms + LIVE_CLOCK_SLACK_MS:
            at_ms = max_ms
        else:
            return f"Time cannot be after {format_ms(max_ms)}.", None

    if side == SIDE_THEM:
        return None, {
            "period": period,
            "at_ms": at_ms,
            "side": SIDE_THEM,
            "scorer_id": None,
            "assist_id": None,
        }

    scorer, err = _parse_player_id(scorer_id, require_scorer, "Scorer")
    if err:
        return err, None
    assist, err = _parse_player_id(assist_id, False, "Assist")
    if err:
        return err, None
    if scorer is not None and scorer not in present_ids:
        return "Scorer has to be at the game.", None
    if assist is not None and assist not in present_ids:
        return "Assist has to be at the game.", None
    if scorer is not None and assist is not None and scorer == assist:
        return "Scorer and assist have to be different people.", None
    return None, {
        "period": period,
        "at_ms": at_ms,
        "side": SIDE_US,
        "scorer_id": scorer,
        "assist_id": assist,
    }


def apply_goal_attrs(goal, attrs):
    goal.period = attrs["period"]
    goal.at_ms = attrs["at_ms"]
    goal.side = attrs["side"]
    goal.scorer_id = attrs["scorer_id"]
    goal.assist_id = attrs["assist_id"]


def create_goal(game, attrs, now=None):
    now = now or datetime.utcnow()
    goal = ScmGoal(game_id=game.id, created_at=now)
    apply_goal_attrs(goal, attrs)
    game.updated_at = now
    return goal


def goal_label(goal, players_by_id):
    if goal.side != SIDE_US:
        return "Them"
    scorer = players_by_id.get(goal.scorer_id)
    assist = players_by_id.get(goal.assist_id)
    scorer_name = player_chip_label(scorer) if scorer is not None else "Unknown"
    if assist is None:
        return scorer_name
    return f"{scorer_name} ({player_chip_label(assist)})"


def goal_warning(goal, events, formation, players_by_id):
    if goal.side != SIDE_US or not goal.scorer_id:
        return None
    if player_on_field_at(
        events, formation, goal.period, goal.at_ms, goal.scorer_id
    ):
        return None
    player = players_by_id.get(goal.scorer_id)
    name = player_chip_label(player) if player is not None else "Scorer"
    return f"{name} was not on the field at {format_ms(goal.at_ms)}."


def goal_rows(goals, players_by_id, events, formation):
    rows = []
    for goal in goals:
        rows.append(
            {
                "id": goal.id,
                "period": int(goal.period),
                "at_ms": int(goal.at_ms or 0),
                "clock": format_ms(goal.at_ms),
                "side": goal.side,
                "scorer_id": goal.scorer_id,
                "assist_id": goal.assist_id,
                "label": goal_label(goal, players_by_id),
                "warning": goal_warning(goal, events, formation, players_by_id),
            }
        )
    return rows
