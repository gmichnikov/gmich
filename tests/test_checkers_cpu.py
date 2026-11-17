import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../app/projects/checkers_online")))

from cpu import choose_move


def _empty():
    return [[None for _ in range(8)] for _ in range(8)]


def _winning_board():
    board = _empty()
    board[2][1] = "b"
    board[3][2] = "r"
    return board


class TestCheckersCpu(unittest.TestCase):
    def test_easy_takes_the_last_piece(self):
        move = choose_move(_winning_board(), "black", "easy")
        self.assertEqual(move["to"], [4, 3])
        self.assertEqual(len(move["captures"]), 1)

    def test_medium_takes_the_last_piece(self):
        move = choose_move(_winning_board(), "black", "medium")
        self.assertEqual(move["to"], [4, 3])

    def test_hard_takes_the_last_piece(self):
        move = choose_move(_winning_board(), "black", "hard")
        self.assertEqual(move["to"], [4, 3])

    def test_search_leaves_the_board_unchanged(self):
        board = _winning_board()
        board[5][4] = "r"
        board[6][5] = "b"
        before = [row[:] for row in board]
        choose_move(board, "black", "hard")
        self.assertEqual(board, before)
