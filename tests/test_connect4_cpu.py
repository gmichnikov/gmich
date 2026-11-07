import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../app/projects/connect4_online")))

from cpu import choose_column


def empty_board():
    return [[None for _ in range(7)] for _ in range(6)]


class TestConnect4Cpu(unittest.TestCase):
    def test_easy_takes_an_immediate_win(self):
        board = empty_board()
        board[5][0] = "O"
        board[5][1] = "O"
        board[5][2] = "O"
        self.assertEqual(choose_column(board, "O", "easy"), 3)

    def test_easy_blocks_an_immediate_loss(self):
        board = empty_board()
        board[5][0] = "X"
        board[5][1] = "X"
        board[5][2] = "X"
        self.assertEqual(choose_column(board, "O", "easy"), 3)

    def test_medium_does_not_play_under_a_winning_line(self):
        board = empty_board()
        board[5] = ["X", "O", "X", None, "O", "X", "O"]
        board[4][0] = "X"
        board[4][1] = "X"
        board[4][2] = "X"
        self.assertNotEqual(choose_column(board, "O", "medium"), 3)

    def test_search_leaves_the_board_unchanged(self):
        board = empty_board()
        board[5][3] = "X"
        before = [row[:] for row in board]
        choose_column(board, "O", "hard")
        self.assertEqual(board, before)
