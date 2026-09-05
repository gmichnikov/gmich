"""Database-backed room engine for Friend Wordle."""

import random
import re
from datetime import datetime, timedelta

from app import db
from app.projects.friend_wordle.models import FriendWordleRoom
from app.utils.wordle.evaluate import evaluate_guess
from app.utils.wordle.word_lists import is_valid_guess

ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
ROOM_CODE_LENGTH = 6
CLEANUP_DAYS = 14
MAX_NAME_LENGTH = 30
MAX_GUESSES = 6
_SECRET_RE = re.compile(r"^[A-Za-z]{5}$")


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


def _empty_guesses():
    return []


def _both_seated(room):
    return room.seat_x is not None and room.seat_o is not None


def _clear_round(room):
    room.secret = None
    room.guesses = _empty_guesses()
    room.role_x = None
    room.role_o = None


def _setter_seat(room):
    if room.role_x == FriendWordleRoom.ROLE_SETTER:
        return "X"
    if room.role_o == FriendWordleRoom.ROLE_SETTER:
        return "O"
    return None


def _guesser_seat(room):
    if room.role_x == FriendWordleRoom.ROLE_GUESSER:
        return "X"
    if room.role_o == FriendWordleRoom.ROLE_GUESSER:
        return "O"
    return None


def cleanup_stale_rooms():
    cutoff = datetime.utcnow() - timedelta(days=CLEANUP_DAYS)
    FriendWordleRoom.query.filter(FriendWordleRoom.updated_at < cutoff).delete()
    db.session.commit()


def _get_room_row(code):
    room = FriendWordleRoom.query.filter_by(code=(code or "").upper()).first()
    if room is None:
        raise RoomError("That game room doesn't exist.", 404)
    return room


def create_room():
    cleanup_stale_rooms()
    for _ in range(20):
        code = _generate_code()
        if FriendWordleRoom.query.filter_by(code=code).first():
            continue
        now = datetime.utcnow()
        room = FriendWordleRoom(
            code=code,
            guesses=_empty_guesses(),
            status=FriendWordleRoom.STATUS_WAITING,
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
            if _both_seated(room) and room.status == FriendWordleRoom.STATUS_WAITING:
                room.status = FriendWordleRoom.STATUS_CHOOSING_ROLES
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


def claim_setter(code, player_id):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can claim a role.", 403)
    if room.status != FriendWordleRoom.STATUS_CHOOSING_ROLES:
        raise RoomError("You can't claim setter right now.", 400)
    if room.role_x or room.role_o:
        raise RoomError("Someone already claimed setter.", 409)

    if seat == "X":
        room.role_x = FriendWordleRoom.ROLE_SETTER
        room.role_o = FriendWordleRoom.ROLE_GUESSER
    else:
        room.role_o = FriendWordleRoom.ROLE_SETTER
        room.role_x = FriendWordleRoom.ROLE_GUESSER

    room.secret = None
    room.guesses = _empty_guesses()
    room.status = FriendWordleRoom.STATUS_SETTING_WORD
    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat


def set_secret(code, player_id, word):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can set the secret word.", 403)
    if room.status != FriendWordleRoom.STATUS_SETTING_WORD:
        raise RoomError("The secret word can't be changed right now.", 400)
    if seat != _setter_seat(room):
        raise RoomError("Only the setter can choose the secret word.", 403)

    cleaned = (word or "").strip()
    if not _SECRET_RE.fullmatch(cleaned):
        raise RoomError("Secret word must be exactly 5 letters (A–Z).", 400)

    room.secret = cleaned.lower()
    _touch(room)
    db.session.commit()
    return room, seat


def confirm_secret(code, player_id):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only seated players can start the round.", 403)
    if room.status != FriendWordleRoom.STATUS_SETTING_WORD:
        raise RoomError("This round can't be started right now.", 400)
    if seat != _setter_seat(room):
        raise RoomError("Only the setter can confirm the secret word.", 403)
    if not room.secret or not _SECRET_RE.fullmatch(room.secret):
        raise RoomError("Enter a 5-letter secret word first.", 400)

    room.status = FriendWordleRoom.STATUS_GUESSING
    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat


def submit_guess(code, player_id, word):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("You're spectating and can't submit guesses.", 403)
    if room.status != FriendWordleRoom.STATUS_GUESSING:
        raise RoomError("This game isn't accepting guesses right now.", 400)
    if seat != _guesser_seat(room):
        raise RoomError("Only the guesser can submit guesses.", 403)
    if not room.secret:
        raise RoomError("The secret word isn't ready yet.", 400)

    guesses = list(room.guesses or [])
    if len(guesses) >= MAX_GUESSES:
        raise RoomError("No guesses remaining.", 400)

    cleaned = (word or "").strip().lower()
    if len(cleaned) != 5:
        raise RoomError("Guess must be exactly 5 letters.", 400)
    if not is_valid_guess(cleaned):
        raise RoomError("Not in word list.", 400)

    feedback = evaluate_guess(cleaned, room.secret)
    guesses.append({"word": cleaned, "feedback": feedback})
    room.guesses = guesses

    if all(status == "correct" for status in feedback):
        room.status = FriendWordleRoom.STATUS_WON
    elif len(guesses) >= MAX_GUESSES:
        room.status = FriendWordleRoom.STATUS_LOST

    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat


def rematch(code, player_id):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("Only players in this room can start a rematch.", 403)
    if room.status not in (FriendWordleRoom.STATUS_WON, FriendWordleRoom.STATUS_LOST):
        raise RoomError("The current round isn't finished yet.", 400)

    _clear_round(room)
    room.status = FriendWordleRoom.STATUS_CHOOSING_ROLES
    room.version += 1
    _touch(room)
    db.session.commit()
    return room, seat
