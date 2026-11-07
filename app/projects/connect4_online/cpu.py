"""Computer opponent for Connect 4 Online."""

import random

CPU_PLAYER_ID = "__cpu__"
CPU_DISPLAY_NAME = "Computer"

ROWS = 6
COLS = 7
WIN_SCORE = 1_000_000
COLUMN_ORDER = (3, 2, 4, 1, 5, 0, 6)
MEDIUM_DEPTH = 4
HARD_DEPTH = 7


def other_seat(seat):
    return "O" if seat == "X" else "X"


def lowest_empty_row(board, col):
    for row in range(ROWS - 1, -1, -1):
        if board[row][col] is None:
            return row
    return None


def _is_board_full(board):
    return all(cell is not None for cell in board[0])


def _count_direction(board, row, col, row_dir, col_dir, seat):
    count = 0
    r = row + row_dir
    c = col + col_dir
    while 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == seat:
        count += 1
        r += row_dir
        c += col_dir
    return count


def _is_win(board, row, col, seat):
    for row_dir, col_dir in ((0, 1), (1, 0), (-1, 1), (1, 1)):
        total = (
            _count_direction(board, row, col, row_dir, col_dir, seat)
            + _count_direction(board, row, col, -row_dir, -col_dir, seat)
            + 1
        )
        if total >= 4:
            return True
    return False


def _score_window(cells, player):
    opponent = other_seat(player)
    mine = sum(1 for cell in cells if cell == player)
    theirs = sum(1 for cell in cells if cell == opponent)
    if mine and theirs:
        return 0
    if mine == 4:
        return 100
    if theirs == 4:
        return -100
    if mine == 3:
        return 12
    if theirs == 3:
        return -16
    if mine == 2:
        return 3
    if theirs == 2:
        return -4
    if mine == 1:
        return 1
    if theirs == 1:
        return -1
    return 0


def _evaluate(board, player):
    opponent = other_seat(player)
    score = 0
    for row in range(ROWS):
        if board[row][3] == player:
            score += 3
        elif board[row][3] == opponent:
            score -= 3

    for row in range(ROWS):
        for col in range(COLS - 3):
            score += _score_window(
                [board[row][col + offset] for offset in range(4)],
                player,
            )
    for col in range(COLS):
        for row in range(ROWS - 3):
            score += _score_window(
                [board[row + offset][col] for offset in range(4)],
                player,
            )
    for row in range(ROWS - 3):
        for col in range(COLS - 3):
            score += _score_window(
                [board[row + offset][col + offset] for offset in range(4)],
                player,
            )
    for row in range(3, ROWS):
        for col in range(COLS - 3):
            score += _score_window(
                [board[row - offset][col + offset] for offset in range(4)],
                player,
            )
    return score


def _minimax(board, depth, alpha, beta, maximizing, player):
    if depth == 0:
        return _evaluate(board, player)

    mover = player if maximizing else other_seat(player)
    value = -10**18 if maximizing else 10**18

    for col in COLUMN_ORDER:
        row = lowest_empty_row(board, col)
        if row is None:
            continue
        board[row][col] = mover
        if _is_win(board, row, col, mover):
            score = (1 if maximizing else -1) * (WIN_SCORE + depth)
        elif _is_board_full(board):
            score = 0
        else:
            score = _minimax(board, depth - 1, alpha, beta, not maximizing, player)
        board[row][col] = None

        if maximizing:
            value = max(value, score)
            alpha = max(alpha, value)
        else:
            value = min(value, score)
            beta = min(beta, value)
        if alpha >= beta:
            break
    return value


def _immediate_win(board, player):
    for col in COLUMN_ORDER:
        row = lowest_empty_row(board, col)
        if row is None:
            continue
        board[row][col] = player
        wins = _is_win(board, row, col, player)
        board[row][col] = None
        if wins:
            return col
    return None


def _legal_columns(board):
    return [col for col in COLUMN_ORDER if lowest_empty_row(board, col) is not None]


def _choose_easy(board, player):
    winning = _immediate_win(board, player)
    if winning is not None:
        return winning
    blocking = _immediate_win(board, other_seat(player))
    if blocking is not None:
        return blocking
    legal = _legal_columns(board)
    if not legal:
        return None
    if random.random() < 0.5:
        return random.choice(legal)
    return legal[0]


def _choose_search(board, player, depth):
    best_score = -10**18
    best_col = None
    for col in COLUMN_ORDER:
        row = lowest_empty_row(board, col)
        if row is None:
            continue
        board[row][col] = player
        if _is_win(board, row, col, player):
            score = WIN_SCORE + depth
        elif _is_board_full(board):
            score = 0
        else:
            score = _minimax(board, depth - 1, -10**18, 10**18, False, player)
        board[row][col] = None
        if score > best_score:
            best_score = score
            best_col = col
    return best_col


def choose_column(board, player, difficulty):
    if difficulty == "easy":
        return _choose_easy(board, player)
    depth = MEDIUM_DEPTH if difficulty == "medium" else HARD_DEPTH
    return _choose_search(board, player, depth)
