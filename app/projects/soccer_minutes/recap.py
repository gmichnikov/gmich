"""Per-game recap: event log copy and editable event stamps."""

from datetime import datetime

from app.projects.soccer_minutes.clock import format_ms
from app.projects.soccer_minutes.field_state import player_chip_label
from app.projects.soccer_minutes.formation_config import normalize_formation
from app.projects.soccer_minutes.live_state import (
    event_assignments,
    field_diff,
    ordered_events,
)

EVENT_TITLES = {
    "period_start": "Start period",
    "field_set": "Go",
    "period_end": "End period",
}


def _slot_names(formation):
    return {
        slot["key"]: slot["name"] for slot in normalize_formation(formation)["slots"]
    }


def kickoff_summary(assignments, formation, players_by_id):
    names = _slot_names(formation)
    parts = []
    for slot in normalize_formation(formation)["slots"]:
        player_id = assignments.get(slot["key"])
        if not player_id:
            continue
        player = players_by_id.get(player_id)
        label = player_chip_label(player) if player is not None else f"#{player_id}"
        parts.append(f"{label} {names.get(slot['key'], slot['key'])}")
    if not parts:
        return ["Empty field"]
    return [", ".join(parts)]


def event_log_rows(events, formation, players_by_id):
    prev_field = {}
    rows = []
    for event in events:
        summary = []
        if event.type == "period_start":
            prev_field = event_assignments(event, formation)
            summary = kickoff_summary(prev_field, formation, players_by_id)
        elif event.type == "field_set":
            nxt = event_assignments(event, formation)
            summary, _warnings = field_diff(
                prev_field, nxt, formation, players_by_id
            )
            if not summary:
                summary = ["Field unchanged"]
            prev_field = nxt
        elif event.type == "period_end":
            summary = ["Period ended"]
        rows.append(
            {
                "id": event.id,
                "period": event.period,
                "at_ms": int(event.at_ms or 0),
                "clock": format_ms(event.at_ms),
                "type": event.type,
                "title": EVENT_TITLES.get(event.type, event.type),
                "summary": summary,
            }
        )
    return rows


def event_time_bounds(events, event_id):
    """Inclusive [lo, hi] for at_ms in this period. hi is None if this is last in the period."""
    target = next((event for event in events if event.id == event_id), None)
    if target is None:
        return None
    same = [event for event in events if event.period == target.period]
    index = next(i for i, event in enumerate(same) if event.id == event_id)
    lo = int(same[index - 1].at_ms or 0) if index > 0 else 0
    hi = int(same[index + 1].at_ms or 0) if index + 1 < len(same) else None
    return lo, hi, target


def update_event_at_ms(game, event_id, at_ms, now=None):
    now = now or datetime.utcnow()
    events = ordered_events(game)
    bounds = event_time_bounds(events, event_id)
    if bounds is None:
        return "Event not found."
    lo, hi, event = bounds
    try:
        at_ms = int(at_ms)
    except (TypeError, ValueError):
        return "Enter a time like 8:00."
    if at_ms < 0:
        return "Time cannot be negative."
    if at_ms < lo:
        return f"Time cannot be before {format_ms(lo)}."
    if hi is not None and at_ms > hi:
        return f"Time cannot be after {format_ms(hi)}."
    event.at_ms = at_ms
    if (
        event.type == "period_end"
        and event.period == game.current_period
        and not game.clock_running
    ):
        game.elapsed_ms = at_ms
    game.updated_at = now
    return None
