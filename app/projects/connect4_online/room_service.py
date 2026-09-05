"""Database-backed room/game engine for Connect 4 Online."""

import random
from datetime import datetime, timedelta

from app import db
from app.projects.connect4_online.colors import default_color_for_seat
from app.projects.connect4_online.models import Connect4OnlineRoom

ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ROOM_CODE_LENGTH = 6
CLEANUP_DAYS = 14
MAX_NAME_LENGTH = 30
ROWS = 6
COLS = 7


class RoomError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _generate_code():
    return "".join(random.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))


def _empty_board():
    return [[None for _ in range(COLS)] for _ in range(ROWS)]


def _normalize_name(name):
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    return cleaned[:MAX_NAME_LENGTH]


def _touch(room):
    room.updated_at = datetime.utcnow()


def _lowest_empty_row(board, col):
    for row in range(ROWS - 1, -1, -1):
        if board[row][col] is None:
            return row
    return None


def _count_direction(board, row, col, row_dir, col_dir, seat):
    count = 0
    r = row + row_dir
    c = col + col_dir
    while 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == seat:
        count += 1
        r += row_dir
        c += col_dir
    return count


def _winning_line(board, row, col, row_dir, col_dir, seat):
    cells = [[row, col]]
    r = row + row_dir
    c = col + col_dir
    while 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == seat:
        cells.append([r, c])
        r += row_dir
        c += col_dir
    r = row - row_dir
    c = col - col_dir
    while 0 <= r < ROWS and 0 <= c < COLS and board[r][c] == seat:
        cells.append([r, c])
        r -= row_dir
        c -= col_dir
    return cells


def _check_winner(board, row, col):
    seat = board[row][col]
    directions = ((0, 1), (1, 0), (-1, 1), (-1, -1))
    for row_dir, col_dir in directions:
        total = (
            _count_direction(board, row, col, row_dir, col_dir, seat)
            + _count_direction(board, row, col, -row_dir, -col_dir, seat)
            + 1
        )
        if total >= 4:
            return seat, _winning_line(board, row, col, row_dir, col_dir, seat)
    return None, None


def _is_board_full(board):
    return all(cell is not None for cell in board[0])


def cleanup_stale_rooms():
    cutoff = datetime.utcnow() - timedelta(days=CLEANUP_DAYS)
    Connect4OnlineRoom.query.filter(Connect4OnlineRoom.updated_at < cutoff).delete()
    db.session.commit()


def _get_room_row(code):
    room = Connect4OnlineRoom.query.filter_by(code=(code or "").upper()).first()
    if room is None:
        raise RoomError("That game room doesn't exist.", 404)
    return room


def create_room(creator_player_id=None):
    cleanup_stale_rooms()
    starter = random.choice(("X", "O"))
    for _ in range(20):
        code = _generate_code()
        if Connect4OnlineRoom.query.filter_by(code=code).first():
            continue
        now = datetime.utcnow()
        room = Connect4OnlineRoom(
            code=code,
            board=_empty_board(),
            turn=starter,
            last_starter=starter,
            status=Connect4OnlineRoom.STATUS_WAITING,
            seat_x=creator_player_id,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.session.add(room)
        db.session.commit()
        return room
    raise RoomError("Could not create a room right now. Please try again.", 500)


def get_room(code):
    return _get_room_row(code)


def join_room(code, player_id, name=None):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    normalized_name = _normalize_name(name)

    if seat is not None:
        if normalized_name is not None:
            if seat == "X":
                room.name_x = normalized_name
            else:
                room.name_o = normalized_name
            _touch(room)
            db.session.commit()
        return room, seat

    for open_seat in ("X", "O"):
        seat_value = room.seat_x if open_seat == "X" else room.seat_o
        if seat_value is None:
            if open_seat == "X":
                room.seat_x = player_id
                if normalized_name is not None:
                    room.name_x = normalized_name
                if room.color_x is None:
                    room.color_x = default_color_for_seat(room, "X")
            else:
                room.seat_o = player_id
                if normalized_name is not None:
                    room.name_o = normalized_name
                if room.color_o is None:
                    room.color_o = default_color_for_seat(room, "O")
            if room.seat_x and room.seat_o:
                room.status = Connect4OnlineRoom.STATUS_ACTIVE
            room.version += 1
            _touch(room)
            db.session.commit()
            return room, open_seat

    return room, None


def get_state(code, player_id):
    room = _get_room_row(code)
    return room, room.seat_for_player(player_id)


def set_color(code, player_id, color):
    from app.projects.connect4_online.colors import ALLOWED_COLORS

    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can change their color.", 403)

    cleaned = (color or "").strip().lower()
    if cleaned not in ALLOWED_COLORS:
        raise RoomError("Pick a color from the list.", 400)

    other_seat = "O" if seat == "X" else "X"
    other_value = room.color_x if other_seat == "X" else room.color_o
    if other_value and cleaned == other_value:
        raise RoomError("That color is already taken by your opponent.", 409)

    if seat == "X":
        room.color_x = cleaned
    else:
        room.color_o = cleaned
    _touch(room)
    db.session.commit()
    return room, seat


def set_name(code, player_id, name):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can change their name.", 403)

    normalized_name = _normalize_name(name)
    if seat == "X":
        room.name_x = normalized_name
    else:
        room.name_o = normalized_name
    _touch(room)
    db.session.commit()
    return room, seat


def make_move(code, player_id, col):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)

    if seat is None:
        raise RoomError("You're spectating this room and can't make moves.", 403)
    if room.status != Connect4OnlineRoom.STATUS_ACTIVE:
        raise RoomError("This game isn't active right now.", 400)
    if room.turn != seat:
        raise RoomError("It's not your turn.", 400)
    if isinstance(col, str) and col.isdigit():
        col = int(col)
    if isinstance(col, float) and col.is_integer():
        col = int(col)
    if not isinstance(col, int) or not (0 <= col < COLS):
        raise RoomError("Invalid column.", 400)

    board = [list(row) for row in room.board]
    row = _lowest_empty_row(board, col)
    if row is None:
        raise RoomError("That column is full.", 400)

    board[row][col] = seat
    room.board = board
    winner, winning_cells = _check_winner(board, row, col)
    if winner is not None:
        room.status = Connect4OnlineRoom.STATUS_WON
        room.winner = winner
        room.winning_cells = winning_cells
    elif _is_board_full(board):
        room.status = Connect4OnlineRoom.STATUS_DRAW
    else:
        room.turn = "O" if seat == "X" else "X"

    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat


def rematch(code, player_id):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)

    if seat is None:
        raise RoomError("Only players in this room can start a rematch.", 403)
    if room.status not in (
        Connect4OnlineRoom.STATUS_WON,
        Connect4OnlineRoom.STATUS_DRAW,
    ):
        raise RoomError("The current game isn't finished yet.", 400)

    new_starter = "O" if room.last_starter == "X" else "X"
    room.board = _empty_board()
    room.winner = None
    room.winning_cells = None
    room.status = Connect4OnlineRoom.STATUS_ACTIVE
    room.turn = new_starter
    room.last_starter = new_starter
    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat
