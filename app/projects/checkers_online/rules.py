"""US checkers, with jumps optional.

Men move and jump one square diagonally forward. Kings move and jump one
square diagonally in any direction. A jump may continue, and a man keeps
jumping only forward. Reaching the far row crowns the piece and ends the turn.
"""

SIZE = 8
BLACK = "black"
RED = "red"
QUIET_DRAW_PLIES = 40

_MAN = {BLACK: "b", RED: "r"}
_KING = {BLACK: "B", RED: "R"}
_COLOR = {"b": BLACK, "B": BLACK, "r": RED, "R": RED}
_KING_DIRS = ((1, -1), (1, 1), (-1, -1), (-1, 1))


def opponent(color):
    return RED if color == BLACK else BLACK


def is_king(piece):
    return piece in ("B", "R")


def piece_color(piece):
    return _COLOR[piece]


def _forward_dirs(color):
    if color == BLACK:
        return ((1, -1), (1, 1))
    return ((-1, -1), (-1, 1))


def _promo_row(color):
    return 7 if color == BLACK else 0


def _on_board(row, col):
    return 0 <= row < SIZE and 0 <= col < SIZE


def _clone(board):
    return [list(row) for row in board]


def initial_board():
    board = [[None for _ in range(SIZE)] for _ in range(SIZE)]
    for row in range(SIZE):
        for col in range(SIZE):
            if (row + col) % 2 != 0:
                continue
            if row <= 2:
                board[row][col] = _MAN[BLACK]
            elif row >= 5:
                board[row][col] = _MAN[RED]
    return board


def position_key(board, turn):
    rows = []
    for row in board:
        rows.append("".join(cell if cell else "." for cell in row))
    return turn + ":" + "/".join(rows)


def board_from_key(key):
    _turn, body = key.split(":", 1)
    board = []
    for row in body.split("/"):
        board.append([None if cell == "." else cell for cell in row])
    return board


def describe_last_move(previous, current):
    """Where the last piece came from, where it landed, and what it jumped."""
    dest = None
    arrived = None
    emptied = []
    for row in range(SIZE):
        for col in range(SIZE):
            before = previous[row][col]
            after = current[row][col]
            if before == after:
                continue
            if after is not None and (before is None or piece_color(before) != piece_color(after)):
                dest = [row, col]
                arrived = piece_color(after)
            elif before is not None and after is None:
                emptied.append((row, col, before))
    if dest is None or arrived is None:
        return None
    origin = None
    captures = []
    for row, col, before in emptied:
        if piece_color(before) == arrived:
            origin = [row, col]
        else:
            captures.append([row, col])
    if origin is None:
        return None
    return {"from": origin, "to": dest, "captures": captures}


def _move(start, path, captures, promote):
    return {
        "from": [start[0], start[1]],
        "to": [path[-1][0], path[-1][1]],
        "path": [[row, col] for row, col in path],
        "captures": [[row, col] for row, col in captures],
        "promote": promote,
    }


def _quiet_moves(board, row, col):
    piece = board[row][col]
    color = piece_color(piece)
    king = is_king(piece)
    directions = _KING_DIRS if king else _forward_dirs(color)
    moves = []
    for d_row, d_col in directions:
        next_row = row + d_row
        next_col = col + d_col
        if not _on_board(next_row, next_col) or board[next_row][next_col] is not None:
            continue
        promote = (not king) and next_row == _promo_row(color)
        moves.append(_move((row, col), [(next_row, next_col)], [], promote))
    return moves


def _jump_moves(board, row, col):
    piece = board[row][col]
    color = piece_color(piece)
    enemy = opponent(color)
    found = []

    def walk(current, crow, ccol, king_now, path, captures):
        directions = _KING_DIRS if king_now else _forward_dirs(color)
        for d_row, d_col in directions:
            mid_row = crow + d_row
            mid_col = ccol + d_col
            land_row = crow + 2 * d_row
            land_col = ccol + 2 * d_col
            if not _on_board(land_row, land_col):
                continue
            mid = current[mid_row][mid_col]
            if mid is None or piece_color(mid) != enemy:
                continue
            if [mid_row, mid_col] in captures:
                continue
            if current[land_row][land_col] is not None:
                continue
            promote = (not king_now) and land_row == _promo_row(color)
            new_path = path + [(land_row, land_col)]
            new_captures = captures + [[mid_row, mid_col]]
            found.append(_move((row, col), new_path, new_captures, promote))
            if promote:
                continue
            nxt = _clone(current)
            nxt[crow][ccol] = None
            nxt[mid_row][mid_col] = None
            nxt[land_row][land_col] = piece if king_now else _MAN[color]
            walk(nxt, land_row, land_col, king_now, new_path, new_captures)

    walk(board, row, col, is_king(piece), [], [])
    return found


def legal_moves(board, color):
    moves = []
    seen = set()
    for row in range(SIZE):
        for col in range(SIZE):
            piece = board[row][col]
            if piece is None or piece_color(piece) != color:
                continue
            for move in _quiet_moves(board, row, col) + _jump_moves(board, row, col):
                key = (
                    tuple(move["from"]),
                    tuple(move["to"]),
                    tuple(tuple(cell) for cell in move["captures"]),
                )
                if key in seen:
                    continue
                seen.add(key)
                moves.append(move)
    return moves


def apply_move(board, move):
    nxt = _clone(board)
    row, col = move["from"]
    piece = nxt[row][col]
    color = piece_color(piece)
    nxt[row][col] = None
    for cap_row, cap_col in move["captures"]:
        nxt[cap_row][cap_col] = None
    end_row, end_col = move["to"]
    nxt[end_row][end_col] = _KING[color] if move["promote"] else piece
    return nxt


def apply_action(board, turn, quiet_plies, history, move):
    nxt_board = apply_move(board, move)
    nxt_quiet = 0 if move["captures"] or move["promote"] else quiet_plies + 1
    nxt_turn = opponent(turn)
    key = position_key(nxt_board, nxt_turn)
    nxt_history = list(history) + [key]
    status = "active"
    winner = None
    reason = None
    if nxt_quiet >= QUIET_DRAW_PLIES:
        status = "draw"
        reason = "quiet"
    elif nxt_history.count(key) >= 3:
        status = "draw"
        reason = "repeat"
    elif not legal_moves(nxt_board, nxt_turn):
        status = "won"
        winner = turn
    return {
        "board": nxt_board,
        "turn": nxt_turn,
        "quiet_plies": nxt_quiet,
        "history": nxt_history,
        "status": status,
        "winner": winner,
        "result_reason": reason,
    }


def find_move(board, color, origin, dest, captures):
    want_caps = tuple(sorted(tuple(cell) for cell in captures))
    matches = []
    for move in legal_moves(board, color):
        if move["from"] != list(origin) or move["to"] != list(dest):
            continue
        got = tuple(sorted(tuple(cell) for cell in move["captures"]))
        if got == want_caps:
            matches.append(move)
    return matches[0] if matches else None


def new_game_state(starter=BLACK):
    board = initial_board()
    return {
        "board": board,
        "turn": starter,
        "quiet_plies": 0,
        "history": [position_key(board, starter)],
        "status": "active",
        "winner": None,
        "result_reason": None,
    }
