from types import SimpleNamespace

from app.projects.soccer_minutes.field_state import (
    assignment_view,
    drop_player_from_assignments,
    player_chip_compact,
    sanitize_assignments,
    suggested_draft_assignments,
)
from app.projects.soccer_minutes.formation_config import default_formation


def test_sanitize_drops_unknown_slots_and_duplicates():
    formation = default_formation()
    present = {1, 2, 3}
    raw = {
        "gk": 1,
        "def_0": 1,
        "nope": 2,
        "fwd_0": 99,
        "mid_0": 2,
    }
    clean = sanitize_assignments(formation, raw, present)
    assert clean["gk"] == 1
    assert "def_0" not in clean
    assert clean["mid_0"] == 2
    assert "fwd_0" not in clean
    assert "nope" not in clean


def test_sanitize_empty_and_junk():
    formation = default_formation()
    assert sanitize_assignments(formation, None, {1}) == {}
    assert sanitize_assignments(formation, {"gk": "x"}, {1}) == {}


def test_drop_player_from_assignments():
    assert drop_player_from_assignments({"gk": 4, "def_0": 7}, 4) == {"def_0": 7}
    assert drop_player_from_assignments({"gk": "4", "def_0": 7}, 4) == {"def_0": 7}
    assert drop_player_from_assignments(None, 4) == {}


def test_event_mentions_player():
    from types import SimpleNamespace
    from app.projects.soccer_minutes.field_state import event_mentions_player

    event = SimpleNamespace(payload={"assignments": {"gk": 4, "fwd_0": 9}})
    assert event_mentions_player(event, 4)
    assert not event_mentions_player(event, 2)
    assert not event_mentions_player(SimpleNamespace(payload={}), 4)


def _view_player(pid, first, last="X", jersey=None):
    return SimpleNamespace(
        id=pid,
        first_name=first,
        last_name=last,
        jersey_number=jersey,
        full_name=f"{first} {last}",
    )


def test_bench_sorted_by_first_name():
    formation = default_formation()
    players = [
        _view_player(1, "Zoe"),
        _view_player(2, "amy"),
        _view_player(3, "Ben"),
        _view_player(4, "Amy", "Z"),
    ]
    view = assignment_view(formation, {"gk": 3}, players, {1, 2, 3, 4})
    assert [person["first_name"] for person in view["bench"]] == ["amy", "Amy", "Zoe"]
    assert [person["id"] for person in view["bench"]] == [2, 4, 1]


def test_player_chip_compact_uses_number_and_three_letters():
    assert player_chip_compact(_view_player(1, "Christopher", jersey="10")) == "10 Chr…"
    assert player_chip_compact(_view_player(2, "Theo")) == "The…"
    assert player_chip_compact(_view_player(3, "Sam")) == "Sam"
    gk = assignment_view(
        default_formation(),
        {"gk": 1},
        [_view_player(1, "Christopher", jersey="10")],
        {1},
    )["bands"][-1]["slots"][0]
    assert gk["player_label"] == "Christopher #10"
    assert gk["player_compact_label"] == "10 Chr…"


def test_suggested_draft_uses_kickoff_not_later_subs():
    from tests.soccer_minutes.test_live_state import _event

    formation = default_formation()
    events = [
        _event("period_start", 1, 0, {"gk": 1, "mid_0": 2, "fwd_0": 3}, 1),
        _event("field_set", 1, 8000, {"gk": 1, "mid_0": 9, "fwd_0": 3}, 2),
    ]
    draft = suggested_draft_assignments(
        events, formation, formation, {1, 2, 3, 9}
    )
    assert draft["gk"] == 1
    assert draft["mid_0"] == 2
    assert draft["fwd_0"] == 3
    assert 9 not in draft.values()


def test_suggested_draft_keeps_matching_slots_only():
    from tests.soccer_minutes.test_live_state import _event

    previous = default_formation()
    events = [
        _event("period_start", 1, 0, {"gk": 1, "mid_0": 2, "mid_3": 4}, 1),
    ]
    draft = suggested_draft_assignments(
        events, previous, default_formation(), {1, 2, 4}
    )
    assert draft["gk"] == 1
    assert draft["mid_0"] == 2
    assert "mid_3" not in draft


def test_suggested_draft_empty_without_kickoff():
    assert (
        suggested_draft_assignments([], default_formation(), default_formation(), {1})
        == {}
    )
