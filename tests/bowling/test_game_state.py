"""Unit tests for bowling game-state helpers."""

import unittest

from app.projects.bowling.game_state import (
    can_add_player,
    can_remove_or_reorder_players,
    can_rename_player,
    get_actionable_frame,
    get_clearable_frame,
    get_current_turn_player_id,
    is_mark_complete_eligible,
    is_player_add_locked,
    max_valid_pins,
)
from app.projects.bowling.models import BowlingGame


def R(frame, roll, pins):
    return {"frame": frame, "roll": roll, "pins": pins}


class TestActionableFrame(unittest.TestCase):
    def test_empty_starts_frame_1(self):
        self.assertEqual(get_actionable_frame([]), 1)

    def test_alice_frames_1_to_4_done_frame_5_blank(self):
        rolls = []
        for f in range(1, 5):
            rolls.extend([R(f, 1, 4), R(f, 2, 3)])
        self.assertEqual(get_actionable_frame(rolls), 5)
        self.assertEqual(get_clearable_frame(rolls), 4)

    def test_in_progress_frame(self):
        rolls = [R(1, 1, 10), R(2, 1, 7)]
        self.assertEqual(get_actionable_frame(rolls), 2)
        self.assertEqual(get_clearable_frame(rolls), 2)


class TestTurnIndicator(unittest.TestCase):
    def test_fewest_completed_frames_wins(self):
        players = [
            {"id": 1, "order_index": 0},
            {"id": 2, "order_index": 1},
        ]
        rolls = {
            1: [R(1, 1, 4), R(1, 2, 3), R(2, 1, 4), R(2, 2, 3)],
            2: [R(1, 1, 4), R(1, 2, 3)],
        }
        self.assertEqual(get_current_turn_player_id(players, rolls), 2)

    def test_tiebreak_order_index(self):
        players = [
            {"id": 1, "order_index": 0},
            {"id": 2, "order_index": 1},
        ]
        rolls = {
            1: [R(1, 1, 4), R(1, 2, 3)],
            2: [R(1, 1, 6), R(1, 2, 2)],
        }
        self.assertEqual(get_current_turn_player_id(players, rolls), 1)

    def test_single_player(self):
        players = [{"id": 42, "order_index": 0}]
        self.assertEqual(get_current_turn_player_id(players, {42: []}), 42)


class TestLocks(unittest.TestCase):
    def test_player_add_locked_on_frame_2_roll_1(self):
        self.assertTrue(is_player_add_locked([[R(2, 1, 7)]]))
        self.assertFalse(is_player_add_locked([[R(1, 1, 10)]]))

    def test_can_add_player_active_before_lock(self):
        self.assertTrue(
            can_add_player(BowlingGame.STATUS_ACTIVE, [[R(1, 1, 10)]])
        )
        self.assertFalse(
            can_add_player(BowlingGame.STATUS_ACTIVE, [[R(2, 1, 3)]])
        )

    def test_setup_only_edits(self):
        self.assertTrue(can_rename_player(BowlingGame.STATUS_SETUP))
        self.assertFalse(can_rename_player(BowlingGame.STATUS_ACTIVE))
        self.assertTrue(can_remove_or_reorder_players(BowlingGame.STATUS_SETUP))
        self.assertFalse(can_remove_or_reorder_players(BowlingGame.STATUS_ACTIVE))


class TestMarkComplete(unittest.TestCase):
    def test_not_eligible_with_pending(self):
        players = [{"id": 1, "order_index": 0}]
        rolls = {1: [R(1, 1, 10), R(2, 1, 10)]}
        self.assertFalse(is_mark_complete_eligible(players, rolls))

    def test_eligible_full_game(self):
        players = [{"id": 1, "order_index": 0}]
        game_rolls = []
        for f in range(1, 10):
            game_rolls.extend([R(f, 1, 4), R(f, 2, 3)])
        game_rolls.extend([R(10, 1, 7), R(10, 2, 2)])
        rolls = {1: game_rolls}
        self.assertTrue(is_mark_complete_eligible(players, rolls))


class TestMaxValidPins(unittest.TestCase):
    def test_second_roll_after_seven(self):
        self.assertEqual(max_valid_pins(1, 2, [R(1, 1, 7)]), 3)

    def test_frame_10_after_strike_non_strike(self):
        self.assertEqual(max_valid_pins(10, 3, [R(10, 1, 10), R(10, 2, 7)]), 3)


if __name__ == "__main__":
    unittest.main()
