from app.projects.soccer_minutes.clock import parse_clock
from app.projects.soccer_minutes.formation_config import default_formation
from app.projects.soccer_minutes.recap import (
    bench_details_by_player,
    bench_intervals,
    field_stretch_map,
    is_on_field_permutation,
    kickoff_summary,
    period_end_times,
    update_event_assignments,
    event_log_rows,
    event_time_bounds,
)
from types import SimpleNamespace
from tests.soccer_minutes.test_live_state import _event, _player


def test_kickoff_summary_lists_filled_slots():
    formation = default_formation()
    players = {1: _player(1, "Sam", "1"), 2: _player(2, "Alex")}
    lines = kickoff_summary({"gk": 1, "fwd_0": 2}, formation, players)
    assert lines == ["Alex ST, Sam #1 GK"]


def test_event_log_uses_diff_for_go():
    formation = default_formation()
    players = {
        1: _player(1, "A"),
        2: _player(2, "B"),
        4: _player(4, "D"),
    }
    events = [
        _event("period_start", 1, 0, {"gk": 1, "fwd_0": 2}, 1),
        _event("field_set", 1, parse_clock("8:00"), {"gk": 1, "fwd_0": 4}, 2),
        _event("period_end", 1, parse_clock("20:00"), event_id=3),
    ]
    rows = event_log_rows(events, formation, players)
    assert rows[0]["title"] == "Start period"
    assert "A GK" in rows[0]["summary"][0]
    assert rows[1]["title"] == ""
    assert rows[1]["clock"] == "8:00"
    assert rows[1]["summary"] == ["D on for B (ST) · bench 8:00"]
    assert rows[2]["title"] == "End period"


def test_event_log_bench_time_from_last_off_in_period():
    formation = default_formation()
    players = {
        1: _player(1, "A"),
        2: _player(2, "B"),
        3: _player(3, "C"),
    }
    events = [
        _event("period_start", 1, 0, {"gk": 1, "fwd_0": 2}, 1),
        _event("field_set", 1, parse_clock("6:00"), {"gk": 1, "fwd_0": 3}, 2),
        _event("field_set", 1, parse_clock("15:00"), {"gk": 1, "fwd_0": 2}, 3),
    ]
    rows = event_log_rows(events, formation, players)
    assert rows[1]["summary"] == ["C on for B (ST) · bench 6:00"]
    assert rows[2]["summary"] == ["B on for C (ST) · bench 9:00"]


def test_bench_intervals_fill_gaps():
    assert bench_intervals([], parse_clock("20:00")) == [(0, parse_clock("20:00"))]
    assert bench_intervals([(0, parse_clock("20:00"))], parse_clock("20:00")) == []
    assert bench_intervals(
        [(parse_clock("8:00"), parse_clock("16:00"))], parse_clock("20:00")
    ) == [(0, parse_clock("8:00")), (parse_clock("16:00"), parse_clock("20:00"))]
    assert bench_intervals(
        [(0, parse_clock("8:00")), (parse_clock("8:00"), parse_clock("12:00"))],
        parse_clock("20:00"),
    ) == [(parse_clock("12:00"), parse_clock("20:00"))]


def test_bench_details_by_player_uses_period_gaps():
    formation = default_formation()
    players = [_player(1, "A"), _player(2, "B"), _player(3, "C")]
    events = [
        _event("period_start", 1, 0, {"gk": 1, "fwd_0": 2}, 1),
        _event("field_set", 1, parse_clock("6:00"), {"gk": 1, "fwd_0": 3}, 2),
        _event("field_set", 1, parse_clock("15:00"), {"gk": 1, "fwd_0": 2}, 3),
        _event("period_end", 1, parse_clock("20:00"), event_id=4),
        _event("period_start", 2, 0, {"gk": 2}, 5),
        _event("period_end", 2, parse_clock("10:00"), event_id=6),
    ]
    details = bench_details_by_player(events, formation, players, {1, 2, 3})
    assert period_end_times(events) == {1: parse_clock("20:00"), 2: parse_clock("10:00")}
    assert details["2"]["bench"] == "9:00"
    assert [item["duration"] for item in details["2"]["stretches"]] == ["9:00"]
    assert details["2"]["stretches"][0]["start"] == "6:00"
    assert details["2"]["stretches"][0]["end"] == "15:00"
    assert details["3"]["stretches"][0]["start"] == "0:00"
    assert details["3"]["stretches"][0]["end"] == "6:00"
    assert details["3"]["stretches"][1]["start"] == "15:00"
    assert details["3"]["stretches"][2]["period"] == 2
    assert details["3"]["bench"] == "21:00"
    assert details["1"]["stretches"][0]["period"] == 2
    assert details["1"]["stretches"][0]["duration"] == "10:00"


def test_event_time_bounds_inclusive_neighbors():
    events = [
        _event("period_start", 1, 0, {"gk": 1}, 1),
        _event("field_set", 1, parse_clock("8:00"), {"gk": 2}, 2),
        _event("period_end", 1, parse_clock("20:00"), event_id=3),
        _event("period_start", 2, 0, {"gk": 2}, 4),
    ]
    lo, hi, event = event_time_bounds(events, 2)
    assert event.id == 2
    assert lo == 0
    assert hi == parse_clock("20:00")
    lo, hi, _event_end = event_time_bounds(events, 3)
    assert lo == parse_clock("8:00")
    assert hi is None
    lo, hi, _start2 = event_time_bounds(events, 4)
    assert lo == 0
    assert hi is None


def test_is_on_field_permutation():
    assert is_on_field_permutation({"gk": 1, "fwd_0": 2}, {"gk": 2, "fwd_0": 1})
    assert not is_on_field_permutation({"gk": 1, "fwd_0": 2}, {"gk": 1, "fwd_0": 3})
    assert not is_on_field_permutation({"gk": 1, "fwd_0": 2}, {"gk": 1})
    assert not is_on_field_permutation({"gk": 1}, {"gk": 1, "fwd_0": 2})


def test_field_stretch_map_uses_next_event_as_end():
    formation = default_formation()
    players = [_player(1, "A"), _player(2, "B"), _player(3, "C")]
    events = [
        _event("period_start", 1, 0, {"gk": 1, "fwd_0": 2}, 1),
        _event("field_set", 1, parse_clock("8:00"), {"gk": 1, "fwd_0": 3}, 2),
        _event("period_end", 1, parse_clock("20:00"), event_id=3),
    ]
    stretches = field_stretch_map(events, formation, players, {1, 2, 3})
    assert stretches[1]["start"] == "0:00"
    assert stretches[1]["end"] == "8:00"
    assert stretches[2]["start"] == "8:00"
    assert stretches[2]["end"] == "20:00"
    assert 3 not in stretches
    assert stretches[1]["assignments"]["fwd_0"] == 2
    assert stretches[2]["assignments"]["fwd_0"] == 3


def test_update_event_assignments_swap_only():
    formation = default_formation()
    start = _event("period_start", 1, 0, {"gk": 1, "fwd_0": 2}, 1)
    events = [start]
    game = SimpleNamespace(
        formation=formation,
        current_period=1,
        clock_running=True,
        pending_assignments={"gk": 1, "fwd_0": 2},
        updated_at=None,
        id=1,
    )
    error = update_event_assignments(
        game, 1, {"gk": 2, "fwd_0": 1}, events=events
    )
    assert error is None
    assert start.payload["assignments"] == {"gk": 2, "fwd_0": 1}
    assert game.pending_assignments == {"gk": 2, "fwd_0": 1}

    error = update_event_assignments(
        game, 1, {"gk": 1, "fwd_0": 3}, events=events
    )
    assert error is not None
    assert start.payload["assignments"] == {"gk": 2, "fwd_0": 1}
