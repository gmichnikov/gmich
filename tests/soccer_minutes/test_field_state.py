from app.projects.soccer_minutes.field_state import (
    drop_player_from_assignments,
    sanitize_assignments,
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
