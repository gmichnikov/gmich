from app.projects.soccer_minutes.clock import parse_clock
from app.projects.soccer_minutes.formation_config import default_formation
from app.projects.soccer_minutes.recap import (
    event_log_rows,
    event_time_bounds,
    kickoff_summary,
)
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
    assert rows[1]["title"] == "Go"
    assert rows[1]["clock"] == "8:00"
    assert "D on for B (ST)" in rows[1]["summary"]
    assert rows[2]["title"] == "End period"


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
