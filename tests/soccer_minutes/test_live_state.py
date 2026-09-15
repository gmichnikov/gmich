from datetime import datetime, timedelta
from types import SimpleNamespace

from app.projects.soccer_minutes.clock import (
    displayed_elapsed_ms,
    format_ms,
    parse_clock,
)
from app.projects.soccer_minutes.formation_config import default_formation
from app.projects.soccer_minutes.live_state import (
    assignments_equal,
    compute_stints,
    current_spells,
    field_diff,
    game_phase,
    max_event_at_ms,
    minutes_rows,
    next_period_to_start,
    replay_live_assignments,
)


def _event(type, period, at_ms, assignments=None, event_id=1):
    return SimpleNamespace(
        id=event_id,
        type=type,
        period=period,
        at_ms=at_ms,
        payload={"assignments": assignments or {}} if type != "period_end" else {},
    )


def _game(**kwargs):
    data = {
        "period_count": 2,
        "current_period": 1,
        "clock_running": False,
        "elapsed_ms": 0,
        "last_resumed_at": None,
        "draft_assignments": {},
        "pending_assignments": None,
        "formation": default_formation(),
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def _player(pid, first, jersey=None):
    return SimpleNamespace(
        id=pid,
        first_name=first,
        last_name="X",
        jersey_number=jersey,
        full_name=f"{first} X",
    )


def test_format_and_parse_clock():
    assert format_ms(0) == "0:00"
    assert format_ms(8 * 60 * 1000 + 15 * 1000) == "8:15"
    assert format_ms(12 * 60 * 1000) == "12:00"
    assert parse_clock("5:00") == 5 * 60 * 1000
    assert parse_clock("12:00") == 12 * 60 * 1000
    assert parse_clock("0:00") == 0
    assert parse_clock("4:30") == 4 * 60 * 1000 + 30 * 1000
    assert parse_clock("99:59") == 99 * 60 * 1000 + 59 * 1000
    assert parse_clock("5:60") is None
    assert parse_clock("nope") is None
    assert parse_clock("") is None


def test_displayed_elapsed_adds_wall_time_while_running():
    start = datetime(2026, 9, 15, 12, 0, 0)
    game = _game(
        clock_running=True,
        elapsed_ms=60 * 1000,
        last_resumed_at=start,
    )
    now = start + timedelta(seconds=30)
    assert displayed_elapsed_ms(game, now) == 90 * 1000
    game.clock_running = False
    game.last_resumed_at = None
    game.elapsed_ms = 90 * 1000
    assert displayed_elapsed_ms(game, now + timedelta(seconds=40)) == 90 * 1000


def test_phase_and_next_period():
    game = _game()
    assert game_phase(game, []) == "setup"
    assert next_period_to_start(game, []) == 1
    start = _event("period_start", 1, 0, {"gk": 1}, 1)
    assert game_phase(game, [start]) == "live"
    assert next_period_to_start(game, [start]) is None
    end = _event("period_end", 1, 1000, event_id=2)
    assert game_phase(game, [start, end]) == "between"
    assert next_period_to_start(game, [start, end]) == 2
    start2 = _event("period_start", 2, 0, {"gk": 1}, 3)
    end2 = _event("period_end", 2, 1000, event_id=4)
    assert game_phase(game, [start, end, start2, end2]) == "done"
    assert next_period_to_start(game, [start, end, start2, end2]) is None


def test_replay_uses_draft_before_kickoff_and_after_period_end():
    formation = default_formation()
    draft = {"gk": 9, "fwd_0": 5}
    assert replay_live_assignments([], draft, formation) == draft
    start = _event("period_start", 1, 0, {"gk": 1, "fwd_0": 2}, 1)
    go = _event("field_set", 1, 8000, {"gk": 1, "fwd_0": 3}, 2)
    assert replay_live_assignments([start, go], draft, formation) == {
        "gk": 1,
        "fwd_0": 3,
    }
    end = _event("period_end", 1, 9000, event_id=3)
    assert replay_live_assignments([start, go, end], draft, formation) == draft


def test_unchanged_stints_stay_open_across_go():
    formation = default_formation()
    start_map = {"gk": 1, "fwd_0": 2, "mid_0": 3}
    after = {"gk": 1, "fwd_0": 4, "mid_0": 3}
    events = [
        _event("period_start", 1, 0, start_map, 1),
        _event("field_set", 1, 8 * 60 * 1000, after, 2),
    ]
    stints = compute_stints(events, formation, open_until_ms=10 * 60 * 1000, open_period=1)
    by_player = {}
    for stint in stints:
        by_player.setdefault(stint.player_id, []).append(stint)
    gk = by_player[1]
    assert len(gk) == 1
    assert gk[0].start_ms == 0
    assert gk[0].end_ms == 10 * 60 * 1000
    assert gk[0].slot_key == "gk"
    fwd_out = by_player[2]
    assert len(fwd_out) == 1
    assert fwd_out[0].end_ms == 8 * 60 * 1000
    fwd_in = by_player[4]
    assert fwd_in[0].start_ms == 8 * 60 * 1000
    assert fwd_in[0].end_ms == 10 * 60 * 1000


def test_minutes_use_go_stamp_not_later_clock():
    formation = default_formation()
    events = [
        _event("period_start", 1, 0, {"gk": 1, "fwd_0": 2}, 1),
        _event("field_set", 1, parse_clock("4:30"), {"gk": 1, "fwd_0": 3}, 2),
        _event("period_end", 1, parse_clock("5:00"), event_id=3),
    ]
    stints = compute_stints(events, formation)
    two = [s for s in stints if s.player_id == 2][0]
    three = [s for s in stints if s.player_id == 3][0]
    assert two.end_ms == parse_clock("4:30")
    assert three.start_ms == parse_clock("4:30")
    assert three.end_ms == parse_clock("5:00")


def test_abc_slide_diff():
    formation = default_formation()
    live = {"fwd_0": 1, "mid_0": 2, "mid_2": 3, "gk": 10}
    pending = {"fwd_0": 4, "mid_0": 5, "mid_2": 2, "gk": 10}
    players = {
        1: _player(1, "A"),
        2: _player(2, "B"),
        3: _player(3, "C"),
        4: _player(4, "D"),
        5: _player(5, "E"),
        10: _player(10, "G"),
    }
    lines, warnings = field_diff(live, pending, formation, players)
    assert "D on for A (ST)" in lines
    assert "C off" in lines
    assert "B LM → RM" in lines
    assert "E on (LM)" in lines
    assert warnings == []
    assert assignments_equal(live, live)
    assert not assignments_equal(live, pending)


def test_swap_diff():
    formation = default_formation()
    live = {"fwd_0": 1, "mid_0": 2}
    pending = {"fwd_0": 2, "mid_0": 1}
    players = {1: _player(1, "A"), 2: _player(2, "B")}
    lines, _warnings = field_diff(live, pending, formation, players)
    assert any("↔" in line for line in lines)
    assert len(lines) == 1


def test_empty_pending_slot_warns():
    formation = default_formation()
    live = {"gk": 1}
    pending = {}
    players = {1: _player(1, "Pat")}
    lines, warnings = field_diff(live, pending, formation, players)
    assert "Pat off" in lines
    assert "GK is empty" in warnings


def test_max_event_at_ms():
    events = [
        _event("period_start", 1, 0, {"gk": 1}, 1),
        _event("field_set", 1, 8000, {"gk": 2}, 2),
        _event("period_start", 2, 0, {"gk": 2}, 3),
    ]
    assert max_event_at_ms(events, 1) == 8000
    assert max_event_at_ms(events, 2) == 0


def test_minutes_rows_omit_absent_and_format():
    formation = default_formation()
    stints = [
        type("S", (), {"player_id": 1, "slot_key": "gk", "period": 1, "start_ms": 0, "end_ms": 60000})(),
    ]
    players = [_player(1, "Sam", "1"), _player(2, "Out")]
    rows = minutes_rows(stints, players, formation, present_ids={1})
    assert len(rows) == 1
    assert rows[0]["total"] == "1:00"
    assert rows[0]["groups"]["gk"] == "1:00"
    assert rows[0]["groups"]["fwd"] == "0:00"
    assert rows[0]["groups_ms"]["gk"] + rows[0]["groups_ms"]["def"] + rows[0]["groups_ms"]["mid"] + rows[0]["groups_ms"]["fwd"] == rows[0]["total_ms"]
    assert rows[0]["slots"][0]["name"] == "GK"
    assert rows[0]["slots"][0]["time"] == "1:00"
    assert rows[0]["first_name"] == "Sam"


def test_current_spells_start_xi_and_sub():
    formation = default_formation()
    start_map = {"gk": 1, "fwd_0": 2}
    present = {1, 2, 3}
    start = _event("period_start", 1, 0, start_map, 1)
    spells = current_spells([start], formation, 1, start_map, present)
    assert spells[1] == {"on_field": True, "since_ms": 0}
    assert spells[2] == {"on_field": True, "since_ms": 0}
    assert spells[3] == {"on_field": False, "since_ms": 0}

    after = {"gk": 1, "fwd_0": 3}
    go = _event("field_set", 1, 8 * 60 * 1000, after, 2)
    spells = current_spells([start, go], formation, 1, after, present)
    assert spells[1] == {"on_field": True, "since_ms": 0}
    assert spells[2] == {"on_field": False, "since_ms": 8 * 60 * 1000}
    assert spells[3] == {"on_field": True, "since_ms": 8 * 60 * 1000}

    period2 = _event("period_start", 2, 0, after, 3)
    spells = current_spells([start, go, period2], formation, 2, after, present)
    assert spells[1] == {"on_field": True, "since_ms": 0}
    assert spells[3] == {"on_field": True, "since_ms": 0}
    assert spells[2] == {"on_field": False, "since_ms": 0}


def test_group_and_slot_minutes_sum_to_total():
    formation = default_formation()
    stints = [
        type("S", (), {"player_id": 1, "slot_key": "gk", "period": 1, "start_ms": 0, "end_ms": 8 * 60 * 1000})(),
        type("S", (), {"player_id": 1, "slot_key": "fwd_0", "period": 1, "start_ms": 8 * 60 * 1000, "end_ms": 20 * 60 * 1000})(),
    ]
    players = [_player(1, "Sam")]
    rows = minutes_rows(stints, players, formation, present_ids={1})
    row = rows[0]
    assert row["total"] == "20:00"
    assert sum(row["groups_ms"].values()) == row["total_ms"]
    assert sum(slot["ms"] for slot in row["slots"]) == row["total_ms"]
    assert row["groups"]["gk"] == "8:00"
    assert row["groups"]["fwd"] == "12:00"
