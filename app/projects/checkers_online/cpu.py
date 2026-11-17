"""Computer opponent for Checkers Online."""

import random

from app.projects.checkers_online.rules import (
    QUIET_DRAW_PLIES,
    apply_move,
    is_king,
    legal_moves,
    opponent,
    piece_color,
)

CPU_PLAYER_ID = "__cpu__"
CPU_DISPLAY_NAME = "Computer"

WIN_SCORE = 1_000_000
MEDIUM_DEPTH = 3
HARD_DEPTH = 5


def _ordered(moves):
    return sorted(moves, key=lambda move: (len(move["captures"]), move["promote"]), reverse=True)


def _evaluate(board, color):
    score = 0
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece is None:
                continue
            owner = piece_color(piece)
            value = 180 if is_king(piece) else 100
            if not is_king(piece):
                value += row * 5 if owner == "black" else (7 - row) * 5
            score += value if owner == color else -value
    return score


def _negamax(board, color, quiet_plies, depth, alpha, beta, ply):
    if quiet_plies >= QUIET_DRAW_PLIES:
        return 0
    moves = legal_moves(board, color)
    if not moves:
        return -WIN_SCORE + ply
    if depth == 0:
        return _evaluate(board, color)

    best = -WIN_SCORE
    for move in _ordered(moves):
        nxt = apply_move(board, move)
        nxt_quiet = 0 if move["captures"] or move["promote"] else quiet_plies + 1
        score = -_negamax(
            nxt,
            opponent(color),
            nxt_quiet,
            depth - 1,
            -beta,
            -alpha,
            ply + 1,
        )
        if score > best:
            best = score
        if best > alpha:
            alpha = best
        if alpha >= beta:
            break
    return best


def _choose_easy(board, color, moves):
    winning = []
    for move in moves:
        nxt = apply_move(board, move)
        if not legal_moves(nxt, opponent(color)):
            winning.append(move)
    if winning:
        return random.choice(winning)
    if random.random() < 0.5:
        return random.choice(moves)
    captures = [move for move in moves if move["captures"]]
    if captures:
        return random.choice(captures)
    return random.choice(moves)


def choose_move(board, color, difficulty, quiet_plies=0):
    moves = legal_moves(board, color)
    if not moves:
        return None
    if difficulty == "easy":
        return _choose_easy(board, color, moves)

    depth = HARD_DEPTH if difficulty == "hard" else MEDIUM_DEPTH
    best_score = -WIN_SCORE * 2
    tied = []
    alpha = -WIN_SCORE * 2
    beta = WIN_SCORE * 2
    for move in _ordered(moves):
        nxt = apply_move(board, move)
        nxt_quiet = 0 if move["captures"] or move["promote"] else quiet_plies + 1
        score = -_negamax(
            nxt,
            opponent(color),
            nxt_quiet,
            depth - 1,
            -beta,
            -alpha,
            1,
        )
        if score > best_score:
            best_score = score
            tied = [move]
            alpha = score
        elif score == best_score:
            tied.append(move)
    return random.choice(tied)
