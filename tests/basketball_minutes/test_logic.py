"""Tests for Basketball Minutes logic and time math."""

import unittest
from types import SimpleNamespace
from app.projects.basketball_minutes.logic import (
    compute_scoring,
    compute_stints_and_minutes,
    format_duration,
    format_remaining_time,
    game_phase,
    parse_time_input,
    replay_lineup,
)


def _event(event_type, period, remaining_seconds, payload=None, event_id=1):
    return SimpleNamespace(
        id=event_id,
        event_type=event_type,
        period=period,
        remaining_seconds=remaining_seconds,
        payload=payload or {},
    )


def _game(**kwargs):
    data = {
        "id": 1,
        "team_id": 1,
        "period_count": 4,
        "period_minutes": 8,
        "current_period": 1,
        "draft_lineup": [1, 2, 3, 4, 5],
        "pending_lineup": None,
    }
    data.update(kwargs)
    return SimpleNamespace(**data)


class TestBasketballMinutesLogic(unittest.TestCase):

    def test_time_parsing(self):
        # Microwave inputs
        self.assertEqual(parse_time_input("530"), 330)
        self.assertEqual(parse_time_input("800"), 480)
        self.assertEqual(parse_time_input("45"), 45)
        self.assertEqual(parse_time_input("0"), 0)

        # Colon inputs
        self.assertEqual(parse_time_input("5:30"), 330)
        self.assertEqual(parse_time_input("0:45"), 45)
        self.assertEqual(parse_time_input("8:00"), 480)

        # Formatting
        self.assertEqual(format_remaining_time(330), "5:30")
        self.assertEqual(format_remaining_time(45), "0:45")
        self.assertEqual(format_remaining_time(0), "0:00")

        # Durations
        self.assertEqual(format_duration(330), "5m 30s")
        self.assertEqual(format_duration(300), "5m")
        self.assertEqual(format_duration(45), "45s")
        self.assertEqual(format_duration(0), "0m")

    def test_game_phase(self):
        g = _game()
        self.assertEqual(game_phase(g, []), "setup")

        e1 = _event("period_start", 1, 480, {"lineup": [1, 2, 3, 4, 5], "period_seconds": 480}, 1)
        self.assertEqual(game_phase(g, [e1]), "live")

        e2 = _event("period_end", 1, 0, {}, 2)
        self.assertEqual(game_phase(g, [e1, e2]), "between")

        e3 = _event("period_end", 4, 0, {"game_over": True}, 3)
        self.assertEqual(game_phase(g, [e1, e2, e3]), "done")

    def test_stints_and_minutes_math(self):
        g = _game(period_minutes=8)
        # Period 1 starts with [1, 2, 3, 4, 5] at 8:00 (480s)
        e1 = _event("period_start", 1, 480, {"lineup": [1, 2, 3, 4, 5], "period_seconds": 480}, 1)
        # At 5:30 (330s), player 5 subs out for player 6 -> [1, 2, 3, 4, 6]
        e2 = _event("sub", 1, 330, {"lineup": [1, 2, 3, 4, 6], "on": [6], "off": [5]}, 2)
        # Period 1 ends at 0:00 (0s)
        e3 = _event("period_end", 1, 0, {}, 3)

        stints, player_seconds, period_player_seconds = compute_stints_and_minutes(g, [e1, e2, e3])

        # Player 5 played 480 - 330 = 150s (2m 30s)
        self.assertEqual(player_seconds[5], 150)
        # Player 6 played 330 - 0 = 330s (5m 30s)
        self.assertEqual(player_seconds[6], 330)
        # Players 1, 2, 3, 4 played all 480s (8m)
        self.assertEqual(player_seconds[1], 480)
        self.assertEqual(player_seconds[2], 480)
        self.assertEqual(player_seconds[3], 480)
        self.assertEqual(player_seconds[4], 480)

    def test_scoring_computation(self):
        g = _game()
        events = [
            _event("period_start", 1, 480, {"lineup": [1, 2, 3, 4, 5]}, 1),
            _event("score", 1, 400, {"player_id": 1, "shot_type": "2pt", "points": 2}, 2),
            _event("score", 1, 350, {"player_id": 2, "shot_type": "3pt", "points": 3}, 3),
            _event("score", 1, 200, {"player_id": 1, "shot_type": "1pt", "points": 1}, 4),
            _event("score", 1, 200, {"player_id": 1, "shot_type": "miss_ft", "points": 0}, 5),
        ]

        total_pts, player_stats = compute_scoring(g, events)
        self.assertEqual(total_pts, 6)  # 2 + 3 + 1 + 0 = 6
        self.assertEqual(player_stats[1]["points"], 3)
        self.assertEqual(player_stats[1]["fg2_made"], 1)
        self.assertEqual(player_stats[1]["ft_made"], 1)
        self.assertEqual(player_stats[1]["ft_miss"], 1)
        self.assertEqual(player_stats[1]["ft_att"], 2)

        self.assertEqual(player_stats[2]["points"], 3)
        self.assertEqual(player_stats[2]["fg3_made"], 1)
