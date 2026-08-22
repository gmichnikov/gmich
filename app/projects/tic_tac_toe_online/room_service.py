"""Database-backed room/game engine for Tic-Tac-Toe Online."""

import random
from datetime import datetime, timedelta

from app import db
from app.projects.tic_tac_toe_online.models import TicTacToeOnlineRoom

ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ROOM_CODE_LENGTH = 6
CLEANUP_DAYS = 14
MAX_NAME_LENGTH = 30

WIN_PATTERNS = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
)


class RoomError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _generate_code():
    return "".join(random.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))


def _empty_board():
    return [None] * 9


def _normalize_name(name):
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    return cleaned[:MAX_NAME_LENGTH]


def _touch(room):
    room.updated_at = datetime.utcnow()


def _check_winner(board):
    for pattern in WIN_PATTERNS:
        a, b, c = pattern
        if board[a] is not None and board[a] == board[b] == board[c]:
            return board[a], list(pattern)
    return None, None


def cleanup_stale_rooms():
    """Delete rooms idle longer than CLEANUP_DAYS (meaningful actions only bump updated_at)."""
    cutoff = datetime.utcnow() - timedelta(days=CLEANUP_DAYS)
    TicTacToeOnlineRoom.query.filter(TicTacToeOnlineRoom.updated_at < cutoff).delete()
    db.session.commit()


def _get_room_row(code):
    room = TicTacToeOnlineRoom.query.filter_by(code=(code or "").upper()).first()
    if room is None:
        raise RoomError("That game room doesn't exist.", 404)
    return room


def create_room():
    cleanup_stale_rooms()
    for _ in range(20):
        code = _generate_code()
        if TicTacToeOnlineRoom.query.filter_by(code=code).first():
            continue
        now = datetime.utcnow()
        room = TicTacToeOnlineRoom(
            code=code,
            board=_empty_board(),
            turn="X",
            last_starter="X",
            status=TicTacToeOnlineRoom.STATUS_WAITING,
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
            else:
                room.seat_o = player_id
                if normalized_name is not None:
                    room.name_o = normalized_name
            if room.seat_x and room.seat_o:
                room.status = TicTacToeOnlineRoom.STATUS_ACTIVE
            room.version += 1
            _touch(room)
            db.session.commit()
            return room, open_seat

    return room, None


def get_state(code, player_id):
    room = _get_room_row(code)
    return room, room.seat_for_player(player_id)


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


def make_move(code, player_id, cell_index):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)

    if seat is None:
        raise RoomError("You're spectating this room and can't make moves.", 403)
    if room.status != TicTacToeOnlineRoom.STATUS_ACTIVE:
        raise RoomError("This game isn't active right now.", 400)
    if room.turn != seat:
        raise RoomError("It's not your turn.", 400)
    if not isinstance(cell_index, int) or not (0 <= cell_index <= 8):
        raise RoomError("Invalid cell.", 400)

    board = list(room.board)
    if board[cell_index] is not None:
        raise RoomError("That cell is already taken.", 400)

    board[cell_index] = seat
    room.board = board
    winner, line = _check_winner(board)
    if winner is not None:
        room.status = TicTacToeOnlineRoom.STATUS_WON
        room.winner = winner
        room.winning_line = line
    elif all(value is not None for value in board):
        room.status = TicTacToeOnlineRoom.STATUS_DRAW
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
    if room.status not in (TicTacToeOnlineRoom.STATUS_WON, TicTacToeOnlineRoom.STATUS_DRAW):
        raise RoomError("The current game isn't finished yet.", 400)

    new_starter = "O" if room.last_starter == "X" else "X"
    room.board = _empty_board()
    room.winner = None
    room.winning_line = None
    room.status = TicTacToeOnlineRoom.STATUS_ACTIVE
    room.turn = new_starter
    room.last_starter = new_starter
    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat
