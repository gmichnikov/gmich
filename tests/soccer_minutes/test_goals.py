from types import SimpleNamespace

from app.projects.soccer_minutes.clock import parse_clock
from app.projects.soccer_minutes.formation_config import default_formation
from app.projects.soccer_minutes.goals import (
    clear_player_from_goal,
    goal_label,
    goal_rows,
    period_goal_max_ms,
    player_on_field_at,
    score_from_goals,
    started_periods,
    validate_goal,
)
from tests.soccer_minutes.test_live_state import _event, _player


def _goal(**kwargs):
    data = {
        "id": 1,
        "period": 1,
        "at_ms": parse_clock("8:00"),
        "side": "us",
        "scorer_id": 2,
        "assist_id": None,
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


def _events():
    return [
        _event("period_start", 1, 0, {"gk": 1, "fwd_0": 2}, 1),
        _event("field_set", 1, parse_clock("8:00"), {"gk": 1, "fwd_0": 3}, 2),
        _event("period_end", 1, parse_clock("20:00"), event_id=3),
    ]


def test_score_from_goals():
    goals = [
        _goal(side="us"),
        _goal(id=2, side="us"),
        _goal(id=3, side="them"),
    ]
    score = score_from_goals(goals)
    assert score["us"] == 2
    assert score["them"] == 1
    assert score["displayed"] == "2–1"
    assert score["has_goals"] is True
    empty = score_from_goals([])
    assert empty["displayed"] == "0–0"
    assert empty["has_goals"] is False


def test_period_goal_max_uses_period_end():
    events = _events()
    assert period_goal_max_ms(events, 1) == parse_clock("20:00")
    assert period_goal_max_ms(events, 2) is None
    assert started_periods(events) == [1]


def test_period_goal_max_uses_live_clock():
    events = [_event("period_start", 1, 0, {"gk": 1}, 1)]
    assert (
        period_goal_max_ms(
            events, 1, displayed_ms=parse_clock("12:00"), current_period=1, phase="live"
        )
        == parse_clock("12:00")
    )


def test_player_on_field_at_follows_subs():
    events = _events()
    formation = default_formation()
    assert player_on_field_at(events, formation, 1, parse_clock("5:00"), 2)
    assert not player_on_field_at(events, formation, 1, parse_clock("5:00"), 3)
    assert player_on_field_at(events, formation, 1, parse_clock("8:00"), 3)
    assert not player_on_field_at(events, formation, 1, parse_clock("8:00"), 2)


def test_validate_us_goal():
    error, attrs = validate_goal(
        side="us",
        period=1,
        at_ms=parse_clock("5:00"),
        scorer_id=2,
        assist_id=1,
        events=_events(),
        present_ids={1, 2, 3},
    )
    assert error is None
    assert attrs["scorer_id"] == 2
    assert attrs["assist_id"] == 1
    assert attrs["side"] == "us"


def test_validate_them_ignores_scorer():
    error, attrs = validate_goal(
        side="them",
        period=1,
        at_ms=parse_clock("14:00"),
        scorer_id=2,
        assist_id=1,
        events=_events(),
        present_ids={1, 2, 3},
    )
    assert error is None
    assert attrs["scorer_id"] is None
    assert attrs["assist_id"] is None
    assert attrs["side"] == "them"


def test_validate_rejects_same_scorer_and_assist():
    error, attrs = validate_goal(
        side="us",
        period=1,
        at_ms=parse_clock("5:00"),
        scorer_id=2,
        assist_id=2,
        events=_events(),
        present_ids={1, 2, 3},
    )
    assert attrs is None
    assert "different" in error


def test_validate_rejects_absent_scorer():
    error, _attrs = validate_goal(
        side="us",
        period=1,
        at_ms=parse_clock("5:00"),
        scorer_id=9,
        assist_id=None,
        events=_events(),
        present_ids={1, 2, 3},
    )
    assert "at the game" in error


def test_validate_rejects_time_after_period_end():
    error, _attrs = validate_goal(
        side="them",
        period=1,
        at_ms=parse_clock("21:00"),
        scorer_id=None,
        assist_id=None,
        events=_events(),
        present_ids={1, 2, 3},
    )
    assert "after 20:00" in error


def test_validate_clamps_live_clock_one_second_ahead():
    events = [_event("period_start", 1, 0, {"gk": 1}, 1)]
    now = parse_clock("8:00")
    error, attrs = validate_goal(
        side="them",
        period=1,
        at_ms=now + 900,
        scorer_id=None,
        assist_id=None,
        events=events,
        present_ids={1},
        displayed_ms=now,
        current_period=1,
        phase="live",
    )
    assert error is None
    assert attrs["at_ms"] == now


def test_validate_still_rejects_live_clock_well_ahead():
    events = [_event("period_start", 1, 0, {"gk": 1}, 1)]
    now = parse_clock("8:00")
    error, attrs = validate_goal(
        side="them",
        period=1,
        at_ms=now + 3000,
        scorer_id=None,
        assist_id=None,
        events=events,
        present_ids={1},
        displayed_ms=now,
        current_period=1,
        phase="live",
    )
    assert attrs is None
    assert "after 8:00" in error


def test_validate_rejects_unstarted_period():
    error, _attrs = validate_goal(
        side="them",
        period=2,
        at_ms=0,
        scorer_id=None,
        assist_id=None,
        events=_events(),
        present_ids={1, 2, 3},
    )
    assert "has not started" in error


def test_validate_requires_scorer_for_us():
    error, _attrs = validate_goal(
        side="us",
        period=1,
        at_ms=parse_clock("5:00"),
        scorer_id="",
        assist_id=None,
        events=_events(),
        present_ids={1, 2, 3},
    )
    assert "Scorer" in error


def test_goal_label_and_warning():
    players = {1: _player(1, "Sam", "1"), 2: _player(2, "Alex")}
    ours = _goal(scorer_id=2, assist_id=1)
    assert goal_label(ours, players) == "Alex (Sam #1)"
    assert goal_label(_goal(side="them"), players) == "Them"
    rows = goal_rows(
        [_goal(at_ms=parse_clock("5:00"), scorer_id=3, assist_id=None)],
        {3: _player(3, "Priya")},
        _events(),
        default_formation(),
    )
    assert "not on the field" in (rows[0]["warning"] or "")


def test_clear_player_from_goal():
    goal = _goal(scorer_id=2, assist_id=1)
    assert clear_player_from_goal(goal, 2) is True
    assert goal.scorer_id is None
    assert goal.assist_id == 1
    assert clear_player_from_goal(goal, 1) is True
    assert goal.assist_id is None
    assert clear_player_from_goal(goal, 9) is False
