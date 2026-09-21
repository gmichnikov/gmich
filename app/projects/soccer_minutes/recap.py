"""Per-game recap: event log copy and editable event stamps."""

from datetime import datetime

from app.projects.soccer_minutes.clock import format_ms
from app.projects.soccer_minutes.field_state import (
    assignment_view,
    coerce_assignment_map,
    player_chip_label,
)
from app.projects.soccer_minutes.formation_config import normalize_formation
from app.projects.soccer_minutes.live_state import (
    assignments_equal,
    compute_stints,
    event_assignments,
    field_diff,
    game_phase,
    ordered_events,
)

EVENT_TITLES = {
    "period_start": "Start period",
    "field_set": "",
    "period_end": "End period",
}


def _slot_names(formation):
    return {
        slot["key"]: slot["name"] for slot in normalize_formation(formation)["slots"]
    }


def _player_label(player_id, players_by_id):
    player = players_by_id.get(player_id)
    if player is not None:
        return player_chip_label(player)
    return f"#{player_id}"


def _bench_since_at_kickoff(assignments, players_by_id):
    on_ids = set(assignments.values())
    return {pid: 0 for pid in players_by_id if pid not in on_ids}


def _update_bench_since(bench_since, prev_field, next_field, at_ms):
    prev_on = set(prev_field.values())
    now_on = set(next_field.values())
    for player_id in prev_on - now_on:
        bench_since[player_id] = int(at_ms)
    for player_id in now_on:
        bench_since.pop(player_id, None)


def _annotate_ons_with_bench(summary, incoming, at_ms, bench_since, players_by_id):
    if not incoming:
        return summary
    labels = sorted(
        ((pid, _player_label(pid, players_by_id)) for pid in incoming),
        key=lambda item: len(item[1]),
        reverse=True,
    )
    annotated = []
    for line in summary:
        extra = ""
        for player_id, name in labels:
            if line.startswith(f"{name} on"):
                since = int(bench_since.get(player_id, 0))
                extra = f" · bench {format_ms(max(0, int(at_ms) - since))}"
                break
        annotated.append(line + extra)
    return annotated


def period_end_times(events, open_until_ms=None, open_period=None):
    ends = {}
    for event in events:
        if event.type == "period_start":
            ends.setdefault(int(event.period), 0)
        elif event.type == "period_end":
            ends[int(event.period)] = int(event.at_ms or 0)
    if open_period is not None and open_until_ms is not None:
        ends[int(open_period)] = max(0, int(open_until_ms))
    return {period: ms for period, ms in ends.items() if ms > 0}


def _merge_intervals(intervals):
    if not intervals:
        return []
    ordered = sorted((int(start), int(end)) for start, end in intervals if end > start)
    if not ordered:
        return []
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def bench_intervals(on_field_intervals, period_ms):
    """Gaps from 0 to period_ms that are not on the field."""
    period_ms = int(period_ms or 0)
    if period_ms <= 0:
        return []
    gaps = []
    cursor = 0
    for start, end in _merge_intervals(on_field_intervals):
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < period_ms:
        gaps.append((cursor, period_ms))
    return gaps


def bench_details_by_player(
    events,
    formation,
    players,
    present_ids,
    open_until_ms=None,
    open_period=None,
):
    stints = compute_stints(
        events,
        formation,
        open_until_ms=open_until_ms,
        open_period=open_period,
    )
    ends = period_end_times(
        events, open_until_ms=open_until_ms, open_period=open_period
    )
    on_by_player_period = {}
    on_ms = {player.id: 0 for player in players if player.id in present_ids}
    for stint in stints:
        if stint.player_id not in on_ms:
            continue
        dur = int(stint.end_ms) - int(stint.start_ms)
        if dur > 0:
            on_ms[stint.player_id] += dur
        on_by_player_period.setdefault(
            (stint.player_id, int(stint.period)), []
        ).append((stint.start_ms, stint.end_ms))

    details = {}
    for player in players:
        if player.id not in present_ids:
            continue
        stretches = []
        bench_ms = 0
        for period, period_ms in sorted(ends.items()):
            gaps = bench_intervals(
                on_by_player_period.get((player.id, period), []), period_ms
            )
            for start, end in gaps:
                dur = end - start
                bench_ms += dur
                stretches.append(
                    {
                        "period": period,
                        "start_ms": start,
                        "end_ms": end,
                        "ms": dur,
                        "start": format_ms(start),
                        "end": format_ms(end),
                        "duration": format_ms(dur),
                    }
                )
        details[str(player.id)] = {
            "id": player.id,
            "label": player_chip_label(player),
            "on_field": format_ms(on_ms.get(player.id, 0)),
            "bench": format_ms(bench_ms),
            "stretches": stretches,
        }
    return details


def _stretch_end_ms(events, field_event, open_until_ms=None, open_period=None):
    for event in events:
        if int(event.period) != int(field_event.period):
            continue
        if event.id <= field_event.id:
            continue
        if event.type in ("field_set", "period_end"):
            return int(event.at_ms or 0)
    if (
        open_period is not None
        and int(open_period) == int(field_event.period)
        and open_until_ms is not None
    ):
        return max(0, int(open_until_ms))
    return None


def is_on_field_permutation(original, proposed):
    """True when the same players stay in the same slots, possibly reordered."""
    if set(original) != set(proposed):
        return False
    return sorted(original.values()) == sorted(proposed.values())


def field_stretch_map(
    events,
    formation,
    players,
    present_ids,
    open_until_ms=None,
    open_period=None,
):
    result = {}
    for event in events:
        if event.type not in ("period_start", "field_set"):
            continue
        assignments = event_assignments(event, formation)
        display_present = set(present_ids) | set(assignments.values())
        view = assignment_view(formation, assignments, players, display_present)
        end_ms = _stretch_end_ms(
            events, event, open_until_ms=open_until_ms, open_period=open_period
        )
        result[event.id] = {
            "event_id": event.id,
            "period": int(event.period),
            "start_ms": int(event.at_ms or 0),
            "end_ms": end_ms,
            "start": format_ms(event.at_ms),
            "end": format_ms(end_ms) if end_ms is not None else "now",
            "assignments": view["assignments"],
            "bands": view["bands"],
        }
    return result


def update_event_assignments(game, event_id, assignments, now=None, events=None):
    now = now or datetime.utcnow()
    events = ordered_events(game, events)
    event = next((item for item in events if item.id == event_id), None)
    if event is None:
        return "Event not found."
    if event.type not in ("period_start", "field_set"):
        return "This event has no field."
    current = event_assignments(event, game.formation)
    proposed = coerce_assignment_map(game.formation, assignments)
    if not is_on_field_permutation(current, proposed):
        return "Swap players who are already on. Don't add or remove anyone."
    event.payload = {"assignments": dict(proposed)}
    last_field = None
    for item in events:
        if item.type in ("period_start", "field_set"):
            last_field = item
    if (
        last_field is not None
        and last_field.id == event.id
        and game_phase(game, events) == "live"
        and assignments_equal(game.pending_assignments or {}, current)
    ):
        game.pending_assignments = dict(proposed)
    game.updated_at = now
    return None


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
    bench_since = {}
    rows = []
    for event in events:
        summary = []
        if event.type == "period_start":
            prev_field = event_assignments(event, formation)
            bench_since = _bench_since_at_kickoff(prev_field, players_by_id)
            summary = kickoff_summary(prev_field, formation, players_by_id)
        elif event.type == "field_set":
            nxt = event_assignments(event, formation)
            incoming = set(nxt.values()) - set(prev_field.values())
            summary, _warnings = field_diff(
                prev_field, nxt, formation, players_by_id
            )
            summary = _annotate_ons_with_bench(
                summary,
                incoming,
                int(event.at_ms or 0),
                bench_since,
                players_by_id,
            )
            if not summary:
                summary = ["Field unchanged"]
            _update_bench_since(bench_since, prev_field, nxt, event.at_ms)
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
