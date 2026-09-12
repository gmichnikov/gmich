from app.projects.baseball_lineup.lineup_config import (
    format_inning_list,
    max_needed_assignments,
    player_avoidable_repeats,
)


def test_max_needed_no_repeat_when_slots_fit_roster():
    assert max_needed_assignments(12, 12) == 1
    assert max_needed_assignments(6, 15) == 1


def test_max_needed_allows_one_extra_when_short_handed():
    assert max_needed_assignments(12, 11) == 2


def test_max_needed_zero_when_unused():
    assert max_needed_assignments(0, 12) == 0
    assert max_needed_assignments(12, 0) == 0


def test_cf_double_warns_with_enough_kids():
    expected = {"CF": [2, 2, 2, 2, 2, 2]}
    codes = {1: "CF", 4: "CF"}
    repeats = player_avoidable_repeats(codes, expected, 6, 12)
    assert repeats == {"CF": [1, 4]}


def test_cf_double_ok_when_eleven_kids():
    expected = {"CF": [2, 2, 2, 2, 2, 2]}
    codes = {1: "CF", 4: "CF"}
    repeats = player_avoidable_repeats(codes, expected, 6, 11)
    assert repeats == {}


def test_cf_triple_warns_even_when_a_double_is_needed():
    expected = {"CF": [2, 2, 2, 2, 2, 2]}
    codes = {1: "CF", 3: "CF", 5: "CF"}
    repeats = player_avoidable_repeats(codes, expected, 6, 11)
    assert repeats == {"CF": [1, 3, 5]}


def test_format_inning_list():
    assert format_inning_list([3]) == "inning 3"
    assert format_inning_list([1, 4]) == "innings 1 and 4"
    assert format_inning_list([1, 3, 5]) == "innings 1, 3, and 5"
