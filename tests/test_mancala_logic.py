import sys
import os
import unittest

# Allow running without importing root app/__init__.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../app/projects/mancala_online")))

from game_logic import (
    apply_move,
    check_game_over,
    determine_winner,
    initial_board,
    sweep_remaining,
)


class TestMancalaLogic(unittest.TestCase):
    def test_initial_board(self):
        board = initial_board()
        self.assertEqual(len(board), 14)
        self.assertEqual(board[6], 0)
        self.assertEqual(board[13], 0)
        for i in range(6):
            self.assertEqual(board[i], 4)
            self.assertEqual(board[i + 7], 4)

    def test_first_move_extra_turn(self):
        # Pit 2 for player X has 4 stones. Sowing drops into 3, 4, 5, 6 (X's store).
        # Since last stone lands in store (6), X gets an extra turn!
        board = initial_board()
        result = apply_move(board, 2, "X")
        self.assertTrue(result["extra_turn"])
        self.assertFalse(result["game_over"])
        self.assertEqual(result["last_pit"], 6)
        self.assertEqual(result["board"][2], 0)
        self.assertEqual(result["board"][3], 5)
        self.assertEqual(result["board"][4], 5)
        self.assertEqual(result["board"][5], 5)
        self.assertEqual(result["board"][6], 1)
        self.assertEqual(result["sown_steps"], [3, 4, 5, 6])

    def test_skips_opponent_store(self):
        # Setup pit 5 with 9 stones.
        # Should sow into: 6 (own store), 7, 8, 9, 10, 11, 12, skip 13 (opp store), 0, 1
        board = [0] * 14
        board[5] = 9
        result = apply_move(board, 5, "X")
        self.assertEqual(result["board"][6], 1)  # Own store gets 1
        self.assertEqual(result["board"][13], 0)  # Opponent store skipped!
        self.assertEqual(result["board"][0], 1)
        self.assertEqual(result["board"][1], 1)
        self.assertFalse(result["extra_turn"])
        self.assertEqual(result["last_pit"], 1)

    def test_game_over_and_sweep(self):
        # 1 stone in pit 5 for X. Pit 0..4 empty.
        # O has 4 stones in pit 7, 0 in rest.
        board = [0] * 14
        board[5] = 1
        board[7] = 4
        result = apply_move(board, 5, "X")
        # Stone dropped into 6 (X's store). All X's pits are now 0. Game over!
        self.assertTrue(result["game_over"])
        # O's 4 stones from pit 7 should be swept into O's store (13)
        self.assertEqual(result["board"][6], 1)
        self.assertEqual(result["board"][13], 4)
        self.assertEqual(result["board"][7], 0)
        self.assertEqual(result["winner"], "O")
        self.assertEqual(result["swept"], {"X": 0, "O": 4})
        self.assertEqual(result["sweep_steps"], [{"from": 7, "to": 13, "count": 4}])


if __name__ == "__main__":
    unittest.main()
