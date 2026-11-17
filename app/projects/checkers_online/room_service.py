"""Database-backed room/game engine for Checkers Online."""

import random
from datetime import datetime, timedelta

from app import db
from app.projects.checkers_online.cpu import CPU_DISPLAY_NAME, CPU_PLAYER_ID, choose_move
from app.projects.checkers_online.models import CheckersOnlineRoom
from app.projects.checkers_online.rules import (
    BLACK,
    RED,
    apply_action,
    find_move,
    new_game_state,
    opponent,
    position_key,
)

DIFFICULTIES = ("easy", "medium", "hard")

ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ROOM_CODE_LENGTH = 4
CLEANUP_DAYS = 14
MAX_NAME_LENGTH = 30
COLORS = (BLACK, RED)


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


def _colors_locked(room):
    if room.status == CheckersOnlineRoom.STATUS_WAITING:
        return False
    if room.status != CheckersOnlineRoom.STATUS_ACTIVE:
        return True
    return len(room.position_history or []) > 1


def cleanup_stale_rooms():
    cutoff = datetime.utcnow() - timedelta(days=CLEANUP_DAYS)
    CheckersOnlineRoom.query.filter(CheckersOnlineRoom.updated_at < cutoff).delete()
    db.session.commit()


def _get_room_row(code):
    room = CheckersOnlineRoom.query.filter_by(code=(code or "").upper()).first()
    if room is None:
        raise RoomError("That game room doesn't exist.", 404)
    return room


def _clean_difficulty(value):
    cleaned = (value or "").strip().lower()
    if cleaned not in DIFFICULTIES:
        return "medium"
    return cleaned


def cpu_first_from_payload(data):
    data = data or {}
    if "first" in data:
        return data.get("first") == "computer"
    return bool(data.get("cpu_first"))


def _maybe_cpu_move(room):
    if not room.vs_cpu or room.status != CheckersOnlineRoom.STATUS_ACTIVE:
        return
    if room.turn != room.color_o:
        return
    move = choose_move(
        room.board,
        room.turn,
        room.difficulty or "medium",
        room.quiet_plies or 0,
    )
    if move is None:
        room.status = CheckersOnlineRoom.STATUS_WON
        room.winner = room.color_x
        room.result_reason = None
        return
    state = apply_action(
        room.board,
        room.turn,
        room.quiet_plies or 0,
        list(room.position_history or []),
        move,
    )
    _store_state(room, state, room.last_starter)


def _store_state(room, state, starter):
    room.board = state["board"]
    room.turn = state["turn"]
    room.last_starter = starter
    room.quiet_plies = state["quiet_plies"]
    room.position_history = state["history"]
    room.winner = state["winner"]
    room.result_reason = state["result_reason"]
    room.status = (
        CheckersOnlineRoom.STATUS_ACTIVE
        if state["status"] == "active"
        else state["status"]
    )


def create_room(creator_player_id=None):
    cleanup_stale_rooms()
    state = new_game_state(BLACK)
    for _ in range(20):
        code = _generate_code()
        if CheckersOnlineRoom.query.filter_by(code=code).first():
            continue
        now = datetime.utcnow()
        room = CheckersOnlineRoom(
            code=code,
            board=state["board"],
            turn=state["turn"],
            last_starter=BLACK,
            status=CheckersOnlineRoom.STATUS_WAITING,
            seat_x=creator_player_id,
            color_x=BLACK,
            color_o=RED,
            quiet_plies=0,
            position_history=state["history"],
            vs_cpu=False,
            difficulty="medium",
            cpu_first=False,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.session.add(room)
        db.session.commit()
        return room
    raise RoomError("Could not create a room right now. Please try again.", 500)


def create_cpu_room(creator_player_id, difficulty="medium", cpu_first=False, color=BLACK):
    cleanup_stale_rooms()
    difficulty = _clean_difficulty(difficulty)
    human_color = color if color in COLORS else BLACK
    cpu_color = opponent(human_color)
    starter = cpu_color if cpu_first else human_color
    state = new_game_state(starter)
    for _ in range(20):
        code = _generate_code()
        if CheckersOnlineRoom.query.filter_by(code=code).first():
            continue
        now = datetime.utcnow()
        room = CheckersOnlineRoom(
            code=code,
            board=state["board"],
            turn=state["turn"],
            last_starter=starter,
            status=CheckersOnlineRoom.STATUS_ACTIVE,
            seat_x=creator_player_id,
            seat_o=CPU_PLAYER_ID,
            name_o=CPU_DISPLAY_NAME,
            color_x=human_color,
            color_o=cpu_color,
            quiet_plies=state["quiet_plies"],
            position_history=state["history"],
            vs_cpu=True,
            difficulty=difficulty,
            cpu_first=bool(cpu_first),
            version=1,
            created_at=now,
            updated_at=now,
        )
        _maybe_cpu_move(room)
        db.session.add(room)
        db.session.commit()
        return room
    raise RoomError("Could not create a room right now. Please try again.", 500)


def get_state(code, player_id):
    room = _get_room_row(code)
    return room, room.seat_for_player(player_id)


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
            if room.seat_x and room.seat_o and room.status == CheckersOnlineRoom.STATUS_WAITING:
                room.status = CheckersOnlineRoom.STATUS_ACTIVE
            room.version += 1
            _touch(room)
            db.session.commit()
            return room, open_seat

    return room, None


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


def set_color(code, player_id, color):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can change their color.", 403)
    if _colors_locked(room):
        raise RoomError("You can change colors before the first move.", 400)

    cleaned = (color or "").strip().lower()
    if cleaned not in COLORS:
        raise RoomError("Pick red or black.", 400)
    if room.color_for_seat(seat) == cleaned:
        return room, seat

    other = opponent(cleaned)
    if seat == "X":
        room.color_x = cleaned
        room.color_o = other
    else:
        room.color_o = cleaned
        room.color_x = other
    if room.vs_cpu and len(room.position_history or []) <= 1:
        starter = room.color_o if room.cpu_first else room.color_x
        room.turn = starter
        room.last_starter = starter
        room.position_history = [position_key(room.board, starter)]
    _maybe_cpu_move(room)
    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat


def _square(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise RoomError(f"Invalid {label}.", 400)
    row, col = value
    if isinstance(row, bool) or isinstance(col, bool):
        raise RoomError(f"Invalid {label}.", 400)
    try:
        row = int(row)
        col = int(col)
    except (TypeError, ValueError):
        raise RoomError(f"Invalid {label}.", 400)
    if not (0 <= row < 8 and 0 <= col < 8):
        raise RoomError(f"Invalid {label}.", 400)
    return [row, col]


def make_move(code, player_id, payload):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("You're spectating this room and can't make moves.", 403)
    if room.status != CheckersOnlineRoom.STATUS_ACTIVE:
        raise RoomError("This game isn't active right now.", 400)

    color = room.color_for_seat(seat)
    if room.turn != color:
        raise RoomError("It's not your turn.", 400)

    data = payload or {}
    origin = _square(data.get("from"), "square")
    dest = _square(data.get("to"), "square")
    raw_caps = data.get("captures") or []
    if not isinstance(raw_caps, list):
        raise RoomError("Invalid move.", 400)
    captures = [_square(cell, "square") for cell in raw_caps]

    move = find_move(room.board, color, origin, dest, captures)
    if move is None:
        raise RoomError("That move isn't legal.", 400)

    state = apply_action(
        room.board,
        room.turn,
        room.quiet_plies,
        room.position_history or [],
        move,
    )
    _store_state(room, state, room.last_starter)
    _maybe_cpu_move(room)
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
        CheckersOnlineRoom.STATUS_WON,
        CheckersOnlineRoom.STATUS_DRAW,
    ):
        raise RoomError("The current game isn't finished yet.", 400)

    if room.vs_cpu:
        starter = room.color_o if room.cpu_first else room.color_x
    else:
        starter = opponent(room.last_starter)
    state = new_game_state(starter)
    _store_state(room, state, starter)
    if room.vs_cpu:
        _maybe_cpu_move(room)
    elif not (room.seat_x and room.seat_o):
        room.status = CheckersOnlineRoom.STATUS_WAITING
    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat


def set_cpu_settings(code, player_id, difficulty, cpu_first):
    room = _get_room_row(code)
    if not room.vs_cpu:
        raise RoomError("This room isn't a computer game.", 400)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only players in this room can change these settings.", 403)
    if room.status == CheckersOnlineRoom.STATUS_ACTIVE:
        raise RoomError("You can change these after the game ends.", 400)

    room.difficulty = _clean_difficulty(difficulty)
    room.cpu_first = bool(cpu_first)
    _touch(room)
    db.session.commit()
    return room, seat
