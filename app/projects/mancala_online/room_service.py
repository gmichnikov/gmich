"""Database-backed room/game service for Mancala Online."""

import random
from datetime import datetime, timedelta

from app import db
from app.projects.mancala_online.game_logic import (
    apply_move,
    initial_board,
    player_pits,
)
from app.projects.mancala_online.models import MancalaOnlineRoom

ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ROOM_CODE_LENGTH = 6
CLEANUP_DAYS = 14
MAX_NAME_LENGTH = 30


class RoomError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _generate_code():
    return "".join(random.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))


def _normalize_name(name):
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    return cleaned[:MAX_NAME_LENGTH]


def _touch(room):
    room.updated_at = datetime.utcnow()


def cleanup_stale_rooms():
    cutoff = datetime.utcnow() - timedelta(days=CLEANUP_DAYS)
    MancalaOnlineRoom.query.filter(MancalaOnlineRoom.updated_at < cutoff).delete()
    db.session.commit()


def _get_room_row(code):
    room = MancalaOnlineRoom.query.filter_by(code=(code or "").upper()).first()
    if room is None:
        raise RoomError("That game room doesn't exist.", 404)
    return room


def create_room(creator_player_id=None):
    cleanup_stale_rooms()
    starter = random.choice(("X", "O"))
    for _ in range(20):
        code = _generate_code()
        if MancalaOnlineRoom.query.filter_by(code=code).first():
            continue
        now = datetime.utcnow()
        room = MancalaOnlineRoom(
            code=code,
            board=initial_board(),
            turn=starter,
            last_starter=starter,
            status=MancalaOnlineRoom.STATUS_WAITING,
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
            else:
                room.seat_o = player_id
                if normalized_name is not None:
                    room.name_o = normalized_name
            if room.seat_x and room.seat_o:
                room.status = MancalaOnlineRoom.STATUS_ACTIVE
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


def make_move(code, player_id, pit_index):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)

    if seat is None:
        raise RoomError("You're spectating this room and can't make moves.", 403)
    if room.status != MancalaOnlineRoom.STATUS_ACTIVE:
        raise RoomError("This game isn't active right now.", 400)
    if room.turn != seat:
        raise RoomError("It's not your turn.", 400)

    if isinstance(pit_index, str) and pit_index.isdigit():
        pit_index = int(pit_index)
    if isinstance(pit_index, float) and pit_index.is_integer():
        pit_index = int(pit_index)

    allowed_pits = player_pits(seat)
    if not isinstance(pit_index, int) or pit_index not in allowed_pits:
        raise RoomError("Please choose one of your own pits.", 400)

    if room.board[pit_index] <= 0:
        raise RoomError("That pit has no stones.", 400)

    res = apply_move(room.board, pit_index, seat)

    room.board = res["board"]
    room.last_move = {
        "seat": seat,
        "pit_index": pit_index,
        "sown_steps": res["sown_steps"],
        "extra_turn": res["extra_turn"],
        "swept": res["swept"],
        "last_pit": res["last_pit"],
    }

    if res["game_over"]:
        if res["winner"] == "draw":
            room.status = MancalaOnlineRoom.STATUS_DRAW
            room.winner = "draw"
        else:
            room.status = MancalaOnlineRoom.STATUS_WON
            room.winner = res["winner"]
    else:
        if not res["extra_turn"]:
            room.turn = "O" if seat == "X" else "X"

    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat


def rematch(code, player_id):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can start a rematch.", 403)

    if room.status not in (MancalaOnlineRoom.STATUS_WON, MancalaOnlineRoom.STATUS_DRAW):
        raise RoomError("Can only rematch after the game ends.", 400)

    next_starter = "O" if room.last_starter == "X" else "X"
    room.board = initial_board()
    room.turn = next_starter
    room.last_starter = next_starter
    room.status = MancalaOnlineRoom.STATUS_ACTIVE
    room.winner = None
    room.last_move = None
    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat
