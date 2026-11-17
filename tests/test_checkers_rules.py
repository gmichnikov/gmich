import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../app/projects/checkers_online")))

from rules import (
    QUIET_DRAW_PLIES,
    apply_action,
    apply_move,
    initial_board,
    legal_moves,
    new_game_state,
)


def _empty():
    return [[None for _ in range(8)] for _ in range(8)]


def _ends(board, color):
    return {tuple(move["to"]) for move in legal_moves(board, color)}


class TestCheckersRules(unittest.TestCase):
    def test_opening_has_twelve_pieces_a_side(self):
        board = initial_board()
        blacks = reds = 0
        for row in board:
            for cell in row:
                if cell == "b":
                    blacks += 1
                elif cell == "r":
                    reds += 1
        self.assertEqual(blacks, 12)
        self.assertEqual(reds, 12)

    def test_a_jump_can_be_ignored(self):
        board = _empty()
        board[2][1] = "b"
        board[3][2] = "r"
        board[4][3] = None
        board[3][0] = None
        ends = _ends(board, "black")
        self.assertIn((4, 3), ends)
        self.assertIn((3, 0), ends)

    def test_man_double_jump_is_forward_only(self):
        board = _empty()
        board[2][1] = "b"
        board[3][2] = "r"
        board[5][4] = "r"
        ends = _ends(board, "black")
        self.assertIn((4, 3), ends)
        self.assertIn((6, 5), ends)
        self.assertNotIn((2, 1), ends)

    def test_man_cannot_jump_backward(self):
        board = _empty()
        board[4][3] = "b"
        board[3][2] = "r"
        self.assertNotIn((2, 1), _ends(board, "black"))

    def test_crowning_ends_the_turn(self):
        board = _empty()
        board[5][2] = "b"
        board[6][3] = "r"
        board[6][5] = "r"
        ends = _ends(board, "black")
        self.assertIn((7, 4), ends)
        self.assertNotIn((5, 6), ends)
        move = next(m for m in legal_moves(board, "black") if m["to"] == [7, 4])
        after = apply_move(board, move)
        self.assertEqual(after[7][4], "B")
        self.assertIsNone(after[6][3])

    def test_king_steps_one_and_may_jump_backward(self):
        board = _empty()
        board[4][3] = "B"
        board[3][4] = None
        board[3][2] = "r"
        ends = _ends(board, "black")
        self.assertIn((5, 4), ends)
        self.assertIn((2, 1), ends)
        self.assertNotIn((6, 5), ends)

    def test_no_moves_loses(self):
        board = _empty()
        board[2][1] = "b"
        board[3][2] = "r"
        state = new_game_state()
        move = next(m for m in legal_moves(board, "black") if m["to"] == [4, 3])
        result = apply_action(board, "black", 0, state["history"], move)
        self.assertEqual(result["status"], "won")
        self.assertEqual(result["winner"], "black")

    def test_forty_quiet_moves_draw(self):
        board = _empty()
        board[0][0] = "b"
        board[7][7] = "r"
        move = next(m for m in legal_moves(board, "black") if m["to"] == [1, 1])
        result = apply_action(board, "black", QUIET_DRAW_PLIES - 1, ["start"], move)
        self.assertEqual(result["status"], "draw")
        self.assertEqual(result["result_reason"], "quiet")

    def test_repeated_position_draws(self):
        board = _empty()
        board[2][1] = "B"
        board[5][6] = "R"
        move = next(m for m in legal_moves(board, "black") if m["to"] == [3, 2])
        after = apply_move(board, move)
        key_board = after
        # Build a history that already contains the upcoming position twice.
        from rules import position_key

        upcoming = position_key(key_board, "red")
        history = ["start", upcoming, upcoming]
        result = apply_action(board, "black", 0, history, move)
        self.assertEqual(result["status"], "draw")
        self.assertEqual(result["result_reason"], "repeat")
