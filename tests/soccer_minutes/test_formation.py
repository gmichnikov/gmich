from app.projects.soccer_minutes.formation_config import (
    default_formation,
    field_size,
    line_counts,
    normalize_formation,
    parse_formation_from_form,
    parse_line_count,
    parse_period_count,
    resize_formation,
    slots_in_group,
)


def test_default_is_seven_a_side_two_three_one():
    formation = default_formation()
    counts = line_counts(formation)
    assert counts == {"gk": 1, "def": 2, "mid": 3, "fwd": 1}
    assert field_size(formation) == 7
    assert [s["name"] for s in slots_in_group(formation, "def")] == ["LB", "RB"]
    assert [s["name"] for s in slots_in_group(formation, "mid")] == ["LM", "CM", "RM"]
    assert [s["name"] for s in slots_in_group(formation, "fwd")] == ["ST"]
    assert slots_in_group(formation, "gk")[0]["name"] == "GK"


def test_resize_to_nine_a_side_keeps_existing_names():
    nine = resize_formation(default_formation(), 3, 3, 2)
    assert field_size(nine) == 9
    names = [s["name"] for s in slots_in_group(nine, "def")]
    assert names == ["LB", "RB", "DEF 3"]
    fwd = [s["name"] for s in slots_in_group(nine, "fwd")]
    assert fwd == ["ST", "FWD 2"]


def test_resize_down_drops_from_the_end():
    nine = resize_formation(default_formation(), 3, 3, 2)
    seven = resize_formation(nine, 2, 3, 1)
    assert [s["name"] for s in slots_in_group(seven, "def")] == ["LB", "RB"]
    assert [s["name"] for s in slots_in_group(seven, "fwd")] == ["ST"]
    assert field_size(seven) == 7


def test_normalize_rebuilds_keys_and_requires_gk():
    messy = {
        "slots": [
            {"key": "x", "group": "fwd", "name": "ST"},
            {"key": "mid_0", "group": "mid", "name": "CM"},
        ]
    }
    clean = normalize_formation(messy)
    assert any(s["key"] == "gk" for s in clean["slots"])
    assert line_counts(clean)["gk"] == 1


def test_parse_period_and_line_counts_clamp():
    assert parse_period_count("2") == 2
    assert parse_period_count("99") == 6
    assert parse_period_count("nope", default=2) == 2
    assert parse_line_count("-1") == 0
    assert parse_line_count("20") == 8


def test_parse_formation_from_form_uses_posted_names():
    class Form(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    form = Form(
        {
            "def_count": "3",
            "mid_count": "3",
            "fwd_count": "2",
            "slot_name_gk": "Keeper",
            "slot_name_def_0": "LB",
            "slot_name_def_1": "CB",
            "slot_name_def_2": "RB",
            "slot_name_mid_0": "LM",
            "slot_name_mid_1": "CM",
            "slot_name_mid_2": "RM",
            "slot_name_fwd_0": "LW",
            "slot_name_fwd_1": "ST",
        }
    )
    formation = parse_formation_from_form(form, default_formation())
    assert field_size(formation) == 9
    assert slots_in_group(formation, "gk")[0]["name"] == "Keeper"
    assert [s["name"] for s in slots_in_group(formation, "fwd")] == ["LW", "ST"]
