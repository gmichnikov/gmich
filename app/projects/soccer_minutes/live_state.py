"""Replay events, clock actions, pending field, minutes, and live-page JSON."""

from collections import namedtuple
from datetime import datetime

from app import db
from app.projects.soccer_minutes.clock import (
    displayed_elapsed_ms,
    format_ms,
    iso_utc,
    parse_clock,
)
from app.projects.soccer_minutes.field_state import (
    assignment_view,
    coerce_assignment_map,
    player_chip_label,
    present_player_ids,
    roster_entries_by_player,
    sanitize_assignments,
)
from app.projects.soccer_minutes.formation_config import GROUPS, normalize_formation
from app.projects.soccer_minutes.models import ScmEvent, ScmPlayer

Stint = namedtuple("Stint", "player_id slot_key period start_ms end_ms")

UNDO_LABELS = {
    "field_set": "Undo Go",
    "period_end": "Undo end period",
    "period_start": "Undo start period",
}


def ordered_events(game, events=None):
    if events is not None:
        return list(events)
    return (
        ScmEvent.query.filter_by(game_id=game.id)
        .order_by(ScmEvent.period, ScmEvent.id)
        .all()
    )


def event_assignments(event, formation):
    payload = event.payload if isinstance(getattr(event, "payload", None), dict) else {}
    return coerce_assignment_map(formation, payload.get("assignments") or {})


def assignments_equal(left, right):
    def canon(raw):
        if not isinstance(raw, dict):
            return {}
        clean = {}
        for key, value in raw.items():
            try:
                clean[str(key)] = int(value)
            except (TypeError, ValueError):
                continue
        return clean

    return canon(left) == canon(right)


def replay_live_assignments(events, draft_assignments, formation):
    """Current on-field map: last field event, or draft after period_end / before kickoff."""
    formation = normalize_formation(formation)
    current = None
    for event in events:
        if event.type in ("period_start", "field_set"):
            current = event_assignments(event, formation)
        elif event.type == "period_end":
            current = None
    if current is None:
        return coerce_assignment_map(formation, draft_assignments)
    return current


def game_phase(game, events=None):
    events = ordered_events(game, events)
    if not any(event.type == "period_start" for event in events):
        return "setup"
    last = events[-1]
    if last.type == "period_end":
        if last.period >= int(game.period_count or 1):
            return "done"
        return "between"
    return "live"


def next_period_to_start(game, events=None):
    events = ordered_events(game, events)
    phase = game_phase(game, events)
    if phase == "setup":
        return 1
    if phase == "between":
        nxt = events[-1].period + 1
        if nxt <= int(game.period_count or 1):
            return nxt
    return None


def max_event_at_ms(events, period):
    values = [int(event.at_ms or 0) for event in events if event.period == period]
    return max(values) if values else 0


def compute_stints(events, formation, open_until_ms=None, open_period=None):
    """Replay field events into stints. Unchanged player+slot stays one stint."""
    formation = normalize_formation(formation)
    closed = []
    open_map = {}

    def apply_field(period, at_ms, assignments):
        next_map = {}
        for slot, player_id in assignments.items():
            prev = open_map.get(slot)
            if prev and prev[0] == player_id and prev[2] == period:
                next_map[slot] = prev
            else:
                next_map[slot] = (player_id, at_ms, period)
        for slot, prev in list(open_map.items()):
            if prev[2] != period:
                continue
            nxt = next_map.get(slot)
            if nxt and nxt[0] == prev[0] and nxt[2] == period:
                continue
            if at_ms > prev[1]:
                closed.append(Stint(prev[0], slot, period, prev[1], at_ms))
        for slot, prev in list(open_map.items()):
            if prev[2] == period:
                del open_map[slot]
        open_map.update(next_map)

    def close_period(period, at_ms):
        for slot, prev in list(open_map.items()):
            if prev[2] != period:
                continue
            if at_ms > prev[1]:
                closed.append(Stint(prev[0], slot, period, prev[1], at_ms))
            del open_map[slot]

    for event in events:
        if event.type in ("period_start", "field_set"):
            apply_field(
                event.period,
                int(event.at_ms or 0),
                event_assignments(event, formation),
            )
        elif event.type == "period_end":
            close_period(event.period, int(event.at_ms or 0))

    if open_until_ms is not None and open_period is not None:
        close_period(open_period, int(open_until_ms))
    return closed


def minutes_rows(stints, players, formation, present_ids):
    formation = normalize_formation(formation)
    slot_group = {slot["key"]: slot["group"] for slot in formation["slots"]}
    rows = []
    by_id = {stint.player_id: [] for stint in stints}
    for stint in stints:
        by_id.setdefault(stint.player_id, []).append(stint)
    for player in players:
        if player.id not in present_ids:
            continue
        groups = {group: 0 for group in GROUPS}
        slot_ms = {}
        total = 0
        for stint in by_id.get(player.id, []):
            dur = stint.end_ms - stint.start_ms
            total += dur
            group = slot_group.get(stint.slot_key)
            if group in groups:
                groups[group] += dur
            slot_ms[stint.slot_key] = slot_ms.get(stint.slot_key, 0) + dur
        slots = []
        for slot in formation["slots"]:
            ms = slot_ms.get(slot["key"], 0)
            if ms:
                slots.append(
                    {
                        "key": slot["key"],
                        "name": slot["name"],
                        "group": slot["group"],
                        "ms": ms,
                        "time": format_ms(ms),
                    }
                )
        rows.append(
            {
                "id": player.id,
                "label": player_chip_label(player),
                "full_name": player.full_name,
                "total_ms": total,
                "total": format_ms(total),
                "groups_ms": groups,
                "groups": {group: format_ms(ms) for group, ms in groups.items()},
                "slots": slots,
            }
        )
    return rows


def field_diff(live, pending, formation, players_by_id):
    """Plain-language pending vs live. Order: swaps, on-for, moves, ons, offs."""
    formation = normalize_formation(formation)
    names = {slot["key"]: slot["name"] for slot in formation["slots"]}
    live = coerce_assignment_map(formation, live)
    pending = coerce_assignment_map(formation, pending)

    def label(player_id):
        player = players_by_id.get(player_id)
        return player_chip_label(player) if player is not None else f"#{player_id}"

    def slot_label(key):
        return names.get(key, key)

    live_pos = {pid: slot for slot, pid in live.items()}
    pend_pos = {pid: slot for slot, pid in pending.items()}
    all_ids = set(live_pos) | set(pend_pos)
    used = set()
    lines = []

    for pid in list(all_ids):
        if pid in used:
            continue
        if pid not in live_pos or pid not in pend_pos:
            continue
        if live_pos[pid] == pend_pos[pid]:
            continue
        old_slot = live_pos[pid]
        new_slot = pend_pos[pid]
        other = live.get(new_slot)
        if (
            other
            and other != pid
            and pend_pos.get(other) == old_slot
            and live_pos.get(other) == new_slot
        ):
            lines.append(
                f"{label(pid)} {slot_label(old_slot)} ↔ {label(other)} {slot_label(new_slot)}"
            )
            used.add(pid)
            used.add(other)

    for slot, pid in pending.items():
        if pid in used:
            continue
        live_pid = live.get(slot)
        if live_pid and live_pid != pid and pid not in live_pos and live_pid not in pend_pos:
            lines.append(
                f"{label(pid)} on for {label(live_pid)} ({slot_label(slot)})"
            )
            used.add(pid)
            used.add(live_pid)

    for pid in all_ids:
        if pid in used:
            continue
        if pid in live_pos and pid in pend_pos and live_pos[pid] != pend_pos[pid]:
            lines.append(
                f"{label(pid)} {slot_label(live_pos[pid])} → {slot_label(pend_pos[pid])}"
            )
            used.add(pid)

    for pid in all_ids:
        if pid in used:
            continue
        if pid in pend_pos and pid not in live_pos:
            lines.append(f"{label(pid)} on ({slot_label(pend_pos[pid])})")
            used.add(pid)

    for pid in all_ids:
        if pid in used:
            continue
        if pid in live_pos and pid not in pend_pos:
            lines.append(f"{label(pid)} off")
            used.add(pid)

    warnings = []
    for slot, pid in live.items():
        if slot not in pending:
            warnings.append(f"{slot_label(slot)} is empty")
    return lines, warnings


def pending_map(game, live, formation, present_ids):
    if game.pending_assignments is None:
        return dict(live)
    return sanitize_assignments(formation, game.pending_assignments, present_ids)


def _players_and_present(team, game):
    players = team.players.order_by(ScmPlayer.sort_order, ScmPlayer.id).all()
    present_ids = present_player_ids(players, roster_entries_by_player(game))
    return players, present_ids


def live_payload(team, game, now=None, urls=None):
    now = now or datetime.utcnow()
    events = ordered_events(game)
    formation = normalize_formation(game.formation)
    players, present_ids = _players_and_present(team, game)
    players_by_id = {player.id: player for player in players}
    phase = game_phase(game, events)
    live = replay_live_assignments(events, game.draft_assignments, formation)
    live = sanitize_assignments(formation, live, present_ids)
    pending = pending_map(game, live, formation, present_ids)
    displayed = displayed_elapsed_ms(game, now)
    period = int(game.current_period or 1)
    min_ms = max_event_at_ms(events, period) if phase == "live" else 0
    open_until = displayed if phase == "live" else None
    open_period = period if phase == "live" else None
    stints = compute_stints(
        events, formation, open_until_ms=open_until, open_period=open_period
    )
    diff, warnings = field_diff(live, pending, formation, players_by_id)
    last = events[-1] if events else None
    live_view = assignment_view(formation, live, players, present_ids)
    pending_view = assignment_view(
        formation, pending, players, present_ids, live_assignments=live
    )
    can_go = phase == "live" and not assignments_equal(live, pending)
    payload = {
        "phase": phase,
        "current_period": period,
        "period_count": int(game.period_count or 1),
        "next_period": next_period_to_start(game, events),
        "clock": {
            "running": bool(game.clock_running) and phase == "live",
            "elapsed_ms": int(game.elapsed_ms or 0),
            "last_resumed_at": iso_utc(game.last_resumed_at)
            if game.clock_running and phase == "live"
            else None,
            "displayed_ms": displayed if phase == "live" else int(game.elapsed_ms or 0),
            "displayed": format_ms(displayed if phase == "live" else game.elapsed_ms),
            "min_ms": min_ms,
            "min_displayed": format_ms(min_ms),
        },
        "live": live_view,
        "pending": pending_view,
        "diff": diff,
        "warnings": warnings,
        "can_go": can_go,
        "minutes": minutes_rows(stints, players, formation, present_ids),
        "undo_label": UNDO_LABELS.get(last.type) if last else None,
        "locked": phase not in ("setup", "between"),
    }
    if urls:
        payload.update(urls)
    return payload


def _touch(game, now):
    game.updated_at = now


def start_period(team, game, now=None):
    now = now or datetime.utcnow()
    events = ordered_events(game)
    phase = game_phase(game, events)
    nxt = next_period_to_start(game, events)
    if nxt is None:
        if phase == "live":
            return "A period is already in progress."
        return "All periods are done."
    players, present_ids = _players_and_present(team, game)
    formation = game.formation
    assignments = sanitize_assignments(
        formation, game.draft_assignments, present_ids
    )
    db.session.add(
        ScmEvent(
            game_id=game.id,
            period=nxt,
            at_ms=0,
            type="period_start",
            payload={"assignments": dict(assignments)},
        )
    )
    game.current_period = nxt
    game.clock_running = True
    game.elapsed_ms = 0
    game.last_resumed_at = now
    game.pending_assignments = dict(assignments)
    _touch(game, now)
    return None


def pause_clock(game, now=None):
    now = now or datetime.utcnow()
    if game_phase(game) != "live":
        return "No period is in progress."
    if game.clock_running:
        game.elapsed_ms = displayed_elapsed_ms(game, now)
        game.clock_running = False
        game.last_resumed_at = None
        _touch(game, now)
    return None


def resume_clock(game, now=None):
    now = now or datetime.utcnow()
    if game_phase(game) != "live":
        return "No period is in progress."
    if not game.clock_running:
        game.clock_running = True
        game.last_resumed_at = now
        _touch(game, now)
    return None


def set_clock(game, target_ms, now=None):
    now = now or datetime.utcnow()
    if game_phase(game) != "live":
        return "Set the clock during a period."
    try:
        target_ms = int(target_ms)
    except (TypeError, ValueError):
        return "Enter a time like 5:00."
    if target_ms < 0:
        return "Time cannot be negative."
    min_ms = max_event_at_ms(ordered_events(game), game.current_period)
    if target_ms < min_ms:
        return f"Cannot set the clock before {format_ms(min_ms)} (latest event)."
    game.elapsed_ms = target_ms
    if game.clock_running:
        game.last_resumed_at = now
    _touch(game, now)
    return None


def save_pending(team, game, assignments):
    if game_phase(game) != "live":
        return "Pending is only used during a period."
    if not isinstance(assignments, dict):
        return "Invalid field assignments."
    players, present_ids = _players_and_present(team, game)
    game.pending_assignments = sanitize_assignments(
        game.formation, assignments, present_ids
    )
    _touch(game, datetime.utcnow())
    return None


def reset_pending(team, game):
    if game_phase(game) != "live":
        return "Reset is only used during a period."
    events = ordered_events(game)
    live = replay_live_assignments(events, game.draft_assignments, game.formation)
    players, present_ids = _players_and_present(team, game)
    live = sanitize_assignments(game.formation, live, present_ids)
    game.pending_assignments = dict(live)
    _touch(game, datetime.utcnow())
    return None


def commit_go(team, game, at_ms=None, now=None):
    now = now or datetime.utcnow()
    events = ordered_events(game)
    if game_phase(game, events) != "live":
        return "Go is only used during a period."
    displayed = displayed_elapsed_ms(game, now)
    stamp = displayed if at_ms is None else int(at_ms)
    if stamp < 0:
        return "Time cannot be negative."
    min_ms = max_event_at_ms(events, game.current_period)
    if stamp < min_ms:
        return f"Cannot stamp before {format_ms(min_ms)} (latest event)."
    players, present_ids = _players_and_present(team, game)
    live = sanitize_assignments(
        game.formation,
        replay_live_assignments(events, game.draft_assignments, game.formation),
        present_ids,
    )
    pending = pending_map(game, live, game.formation, present_ids)
    if assignments_equal(live, pending):
        return "Nothing to commit."
    db.session.add(
        ScmEvent(
            game_id=game.id,
            period=game.current_period,
            at_ms=stamp,
            type="field_set",
            payload={"assignments": dict(pending)},
        )
    )
    game.pending_assignments = dict(pending)
    _touch(game, now)
    return None


def end_period(game, team, now=None):
    now = now or datetime.utcnow()
    events = ordered_events(game)
    if game_phase(game, events) != "live":
        return "No period is in progress."
    players, present_ids = _players_and_present(team, game)
    live = sanitize_assignments(
        game.formation,
        replay_live_assignments(events, game.draft_assignments, game.formation),
        present_ids,
    )
    pending = pending_map(game, live, game.formation, present_ids)
    if not assignments_equal(live, pending):
        return "Reset or Go before ending the period."
    stamp = displayed_elapsed_ms(game, now)
    min_ms = max_event_at_ms(events, game.current_period)
    if stamp < min_ms:
        return f"Cannot end before {format_ms(min_ms)} (latest event)."
    db.session.add(
        ScmEvent(
            game_id=game.id,
            period=game.current_period,
            at_ms=stamp,
            type="period_end",
            payload={},
        )
    )
    game.clock_running = False
    game.elapsed_ms = stamp
    game.last_resumed_at = None
    game.draft_assignments = dict(live)
    game.pending_assignments = None
    _touch(game, now)
    return None


def undo_last(game, now=None):
    now = now or datetime.utcnow()
    events = ordered_events(game)
    if not events:
        return "Nothing to undo."
    last = events[-1]
    db.session.delete(last)
    db.session.flush()
    remaining = [event for event in events if event.id != last.id]

    if last.type == "field_set":
        _touch(game, now)
        return None

    if last.type == "period_end":
        game.current_period = last.period
        game.clock_running = False
        game.elapsed_ms = int(last.at_ms or 0)
        game.last_resumed_at = None
        live = replay_live_assignments(
            remaining, game.draft_assignments, game.formation
        )
        game.pending_assignments = dict(live)
        _touch(game, now)
        return None

    if last.type == "period_start":
        game.clock_running = False
        game.elapsed_ms = 0
        game.last_resumed_at = None
        game.pending_assignments = None
        game.current_period = last.period - 1 if last.period > 1 else 1
        _touch(game, now)
        return None

    _touch(game, now)
    return None


def parse_action_clock(data, fallback_ms):
    if data.get("at_ms") is not None and data.get("at_ms") != "":
        try:
            return int(data.get("at_ms")), None
        except (TypeError, ValueError):
            return None, "Enter a time like 5:00."
    if data.get("clock"):
        parsed = parse_clock(data.get("clock"))
        if parsed is None:
            return None, "Enter a time like 5:00."
        return parsed, None
    return fallback_ms, None
