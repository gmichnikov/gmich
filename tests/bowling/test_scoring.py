"""Unit tests for bowling scoring engine."""

import unittest

from app.projects.bowling.scoring import (
    compute_player_scorecard,
    format_roll_display,
    frame_10_third_roll_locked,
    frame_is_complete,
)


def R(frame, roll, pins):
    return {"frame": frame, "roll": roll, "pins": pins}


class TestFormatRollDisplay(unittest.TestCase):
    def test_gutter(self):
        self.assertEqual(format_roll_display(1, 1, 0, None), "–")

    def test_strike(self):
        self.assertEqual(format_roll_display(3, 1, 10, None), "X")

    def test_spare(self):
        self.assertEqual(format_roll_display(3, 2, 3, 7), "/")

    def test_open(self):
        self.assertEqual(format_roll_display(3, 2, 3, 4), "3")


class TestFrameIsComplete(unittest.TestCase):
    def test_open_incomplete(self):
        self.assertFalse(frame_is_complete(1, {1: 7}))

    def test_strike_complete(self):
        self.assertTrue(frame_is_complete(1, {1: 10}))

    def test_frame_10_open_complete(self):
        self.assertTrue(frame_is_complete(10, {1: 7, 2: 2}))

    def test_frame_10_open_rejects_third_roll_for_completion(self):
        self.assertTrue(frame_is_complete(10, {1: 7, 2: 2}))
        self.assertFalse(frame_is_complete(10, {1: 7}))

    def test_frame_10_strike_needs_three(self):
        self.assertFalse(frame_is_complete(10, {1: 10, 2: 10}))


class TestScoring(unittest.TestCase):
    def test_open_frame(self):
        card = compute_player_scorecard([R(1, 1, 4), R(1, 2, 3)])
        self.assertEqual(card.frames[0].frame_score, 7)
        self.assertEqual(card.frames[0].cumulative, 7)
        self.assertFalse(card.frames[0].pending)

    def test_strike_then_open(self):
        card = compute_player_scorecard(
            [R(1, 1, 10), R(2, 1, 3), R(2, 2, 4)]
        )
        self.assertEqual(card.frames[0].frame_score, 17)
        self.assertEqual(card.frames[0].cumulative, 17)

    def test_spare(self):
        card = compute_player_scorecard(
            [R(1, 1, 7), R(1, 2, 3), R(2, 1, 5), R(2, 2, 0)]
        )
        self.assertEqual(card.frames[0].frame_score, 15)
        self.assertEqual(card.frames[0].rolls[1].display, "/")

    def test_pending_strike_bonus(self):
        card = compute_player_scorecard([R(1, 1, 10), R(2, 1, 10)])
        self.assertTrue(card.frames[0].pending)
        self.assertIsNone(card.frames[0].frame_score)
        self.assertIsNone(card.total)

    def test_consecutive_strikes(self):
        rolls = [
            R(1, 1, 10),
            R(2, 1, 10),
            R(3, 1, 10),
            R(4, 1, 5),
            R(4, 2, 0),
        ]
        card = compute_player_scorecard(rolls)
        self.assertEqual(card.frames[0].frame_score, 30)
        self.assertEqual(card.frames[1].frame_score, 25)

    def test_prd_bob_partial(self):
        """Bob from PRD scorecard: 6+2 in F1, strike in F2 (pending)."""
        card = compute_player_scorecard([R(1, 1, 6), R(1, 2, 2), R(2, 1, 10)])
        self.assertEqual(card.frames[0].frame_score, 8)
        self.assertEqual(card.frames[0].cumulative, 8)
        self.assertTrue(card.frames[1].pending)
        self.assertEqual(card.total, 8)

    def test_prd_alice_partial(self):
        """Alice from PRD: X, 7/, 4+3 through frame 3."""
        card = compute_player_scorecard(
            [
                R(1, 1, 10),
                R(2, 1, 7),
                R(2, 2, 3),
                R(3, 1, 4),
                R(3, 2, 3),
            ]
        )
        self.assertEqual(card.frames[0].frame_score, 20)
        self.assertEqual(card.frames[1].frame_score, 14)
        self.assertEqual(card.frames[1].cumulative, 34)
        self.assertEqual(card.frames[2].frame_score, 7)
        self.assertEqual(card.frames[2].cumulative, 41)
        self.assertEqual(card.total, 41)

    def test_frame_10_strike_strike_strike(self):
        rolls = [R(f, 1, 10) for f in range(1, 10)]
        rolls += [R(10, 1, 10), R(10, 2, 10), R(10, 3, 10)]
        card = compute_player_scorecard(rolls)
        self.assertEqual(card.total, 300)

    def test_frame_10_strike_seven_two(self):
        card = compute_player_scorecard([R(10, 1, 10), R(10, 2, 7), R(10, 3, 2)])
        self.assertEqual(card.frames[9].frame_score, 19)
        self.assertEqual(card.total, 19)

    def test_frame_10_spare_third_roll(self):
        card = compute_player_scorecard([R(10, 1, 7), R(10, 2, 3), R(10, 3, 10)])
        self.assertEqual(card.frames[9].frame_score, 20)
        self.assertFalse(card.frames[9].third_roll_locked)

    def test_frame_10_open_two_rolls(self):
        card = compute_player_scorecard([R(10, 1, 7), R(10, 2, 1)])
        self.assertTrue(frame_10_third_roll_locked({1: 7, 2: 1}))
        self.assertEqual(card.frames[9].frame_score, 8)
        self.assertEqual(len(card.frames[9].rolls), 2)

    def test_clear_pending_bonus_reverts(self):
        before = compute_player_scorecard([R(1, 1, 10), R(2, 1, 7), R(2, 2, 3)])
        self.assertFalse(before.frames[0].pending)

        after = compute_player_scorecard([R(1, 1, 10), R(2, 1, 7)])
        self.assertTrue(after.frames[0].pending)


if __name__ == "__main__":
    unittest.main()
