from app.projects.baseball_lineup.lineup_grid import normalize_cells_payload


def test_blank_later_innings_are_saved_as_omissions():
    payload = [
        {"player_id": 1, "inning": 1, "position_code": "CF"},
        {"player_id": 1, "inning": 4, "position_code": "SS"},
        {"player_id": 1, "inning": 5, "position_code": ""},
        {"player_id": 1, "inning": 6, "position_code": None},
    ]
    assert normalize_cells_payload(payload, [1], 6) == [
        {"player_id": 1, "inning": 1, "position_code": "CF"},
        {"player_id": 1, "inning": 4, "position_code": "SS"},
    ]


def test_duplicate_player_inning_keeps_the_last_position():
    payload = [
        {"player_id": 1, "inning": 2, "position_code": "SS"},
        {"player_id": 1, "inning": 2, "position_code": "2B"},
    ]
    assert normalize_cells_payload(payload, [1], 6) == [
        {"player_id": 1, "inning": 2, "position_code": "2B"}
    ]


def test_invalid_cells_are_dropped_instead_of_failing():
    payload = [
        "nope",
        {"inning": 1},
        {"player_id": "x", "inning": 1, "position_code": "CF"},
        {"player_id": 9, "inning": 1, "position_code": "CF"},
        {"player_id": 1, "inning": 7, "position_code": "CF"},
        {"player_id": 1, "inning": 1, "position_code": "NotAPosition"},
        {"player_id": 1, "inning": 3, "position_code": " Bench "},
    ]
    assert normalize_cells_payload(payload, [1], 6) == [
        {"player_id": 1, "inning": 3, "position_code": "Bench"}
    ]
