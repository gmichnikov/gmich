import random
from datetime import datetime, timedelta

from app import db
from app.projects.codenames_online.confusing_words import tag_confusing
from app.projects.codenames_online.game_logic import (
    apply_guess,
    generate_key,
    pick_board_words,
    pick_replacement_word,
)
from app.projects.codenames_online.models import CodenamesOnlineRoom
from app.projects.codenames_online.word_lists import (
    BOARD_SIZE,
    default_word_list_id,
    list_word_lists,
)

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


def _touch(room):
    room.updated_at = datetime.utcnow()


def _bump(room):
    room.version += 1
    _touch(room)


def _get_room_row(code):
    normalized = (code or "").strip().upper()
    room = CodenamesOnlineRoom.query.filter_by(code=normalized).first()
    if not room:
        raise RoomError("Room not found.", 404)
    return room


def _require_seat(room, player_id):
    seat = room.seat_for_player(player_id)
    if seat is None:
        raise RoomError("You are not in this room.", 403)
    return seat


def _require_clue_giver(room, player_id):
    seat = _require_seat(room, player_id)
    if room.phone_role_for_seat(seat) != CodenamesOnlineRoom.ROLE_CLUE_GIVER:
        raise RoomError("Only the clue-giver phone can do that.", 403)
    return seat


def _require_guesser(room, player_id):
    seat = _require_seat(room, player_id)
    if room.phone_role_for_seat(seat) != CodenamesOnlineRoom.ROLE_GUESSER:
        raise RoomError("Only the guesser phone can do that.", 403)
    return seat


def _sync_waiting_status(room):
    if not room.both_seats_filled():
        room.status = CodenamesOnlineRoom.STATUS_WAITING_DEVICES
    elif not room.roles_assigned():
        room.status = CodenamesOnlineRoom.STATUS_WAITING_ROLES
    elif room.status in (
        CodenamesOnlineRoom.STATUS_WAITING_DEVICES,
        CodenamesOnlineRoom.STATUS_WAITING_ROLES,
        CodenamesOnlineRoom.STATUS_PREVIEW,
        CodenamesOnlineRoom.STATUS_ACTIVE,
        CodenamesOnlineRoom.STATUS_WON,
    ):
        if room.status in (
            CodenamesOnlineRoom.STATUS_PREVIEW,
            CodenamesOnlineRoom.STATUS_ACTIVE,
            CodenamesOnlineRoom.STATUS_WON,
        ):
            return
        room.status = CodenamesOnlineRoom.STATUS_WAITING_START


def _validate_word_list_id(word_list_id):
    lists = {entry["id"] for entry in list_word_lists()}
    if word_list_id not in lists:
        raise RoomError("Unknown word list.", 400)


def _validate_name(name, label):
    cleaned = (name or "").strip()
    if not cleaned:
        raise RoomError(f"{label} is required.", 400)
    if len(cleaned) > MAX_NAME_LENGTH:
        raise RoomError(f"{label} must be {MAX_NAME_LENGTH} characters or fewer.", 400)
    return cleaned


def _deal_preview(room):
    word_list_id = room.word_list_id or default_word_list_id()
    _validate_word_list_id(word_list_id)
    try:
        words = pick_board_words(word_list_id, room.exclude_confusing)
    except ValueError as exc:
        raise RoomError(str(exc), 400) from exc
    key, first_turn = generate_key()
    room.words = words
    room.key = key
    room.revealed = [False] * BOARD_SIZE
    room.turn = first_turn
    room.winner = None
    room.status = CodenamesOnlineRoom.STATUS_PREVIEW
    room.word_list_id = word_list_id


def cleanup_stale_rooms():
    cutoff = datetime.utcnow() - timedelta(days=CLEANUP_DAYS)
    CodenamesOnlineRoom.query.filter(CodenamesOnlineRoom.updated_at < cutoff).delete()
    db.session.commit()


def create_room(creator_player_id=None):
    cleanup_stale_rooms()
    for _ in range(20):
        code = _generate_code()
        if CodenamesOnlineRoom.query.filter_by(code=code).first():
            continue
        now = datetime.utcnow()
        room = CodenamesOnlineRoom(
            code=code,
            seat_x=creator_player_id,
            word_list_id=default_word_list_id(),
            exclude_confusing=True,
            status=CodenamesOnlineRoom.STATUS_WAITING_DEVICES,
            version=1,
            created_at=now,
            updated_at=now,
        )
        db.session.add(room)
        db.session.commit()
        return room
    raise RoomError("Could not create a room right now. Please try again.", 500)


def join_room(code, player_id):
    room = _get_room_row(code)
    seat = room.seat_for_player(player_id)
    if seat is not None:
        return room, seat

    for open_seat in ("X", "O"):
        seat_value = room.seat_x if open_seat == "X" else room.seat_o
        if seat_value is None:
            if open_seat == "X":
                room.seat_x = player_id
            else:
                room.seat_o = player_id
            _sync_waiting_status(room)
            _bump(room)
            db.session.commit()
            return room, open_seat

    return room, None


def get_state(code, player_id):
    room = _get_room_row(code)
    return room, room.seat_for_player(player_id)


def claim_role(code, player_id, role=None, swap=False):
    room = _get_room_row(code)
    seat = _require_seat(room, player_id)

    if room.status not in (
        CodenamesOnlineRoom.STATUS_WAITING_ROLES,
        CodenamesOnlineRoom.STATUS_WAITING_START,
        CodenamesOnlineRoom.STATUS_PREVIEW,
    ):
        raise RoomError("Phone roles cannot be changed now.", 400)

    if swap:
        if not room.roles_assigned():
            raise RoomError("Roles are not assigned yet.", 400)
        if room.status == CodenamesOnlineRoom.STATUS_PREVIEW:
            room.words = None
            room.key = None
            room.revealed = None
            room.turn = None
            room.winner = None
            room.status = CodenamesOnlineRoom.STATUS_WAITING_START
        room.phone_role_x, room.phone_role_o = room.phone_role_o, room.phone_role_x
        _bump(room)
        db.session.commit()
        return room, seat

    if not room.both_seats_filled():
        raise RoomError("Waiting for the second device.", 400)
    if room.roles_assigned():
        raise RoomError("Phone roles are already assigned.", 400)
    if role != CodenamesOnlineRoom.ROLE_CLUE_GIVER:
        raise RoomError("Tap to claim the clue-giver phone.", 400)

    other = "O" if seat == "X" else "X"
    if seat == "X":
        room.phone_role_x = CodenamesOnlineRoom.ROLE_CLUE_GIVER
        room.phone_role_o = CodenamesOnlineRoom.ROLE_GUESSER
    else:
        room.phone_role_o = CodenamesOnlineRoom.ROLE_CLUE_GIVER
        room.phone_role_x = CodenamesOnlineRoom.ROLE_GUESSER

    room.status = CodenamesOnlineRoom.STATUS_WAITING_START
    _bump(room)
    db.session.commit()
    return room, seat


def setup_room(code, player_id, word_list_id=None, name_red=None, name_blue=None, exclude_confusing=None):
    room = _get_room_row(code)
    _require_clue_giver(room, player_id)

    if room.status not in (
        CodenamesOnlineRoom.STATUS_WAITING_START,
        CodenamesOnlineRoom.STATUS_PREVIEW,
        CodenamesOnlineRoom.STATUS_WON,
    ):
        raise RoomError("Setup is not available right now.", 400)

    if word_list_id is not None:
        _validate_word_list_id(word_list_id)
        room.word_list_id = word_list_id
    if name_red is not None:
        room.name_red = _validate_name(name_red, "Red spymaster name")
    if name_blue is not None:
        room.name_blue = _validate_name(name_blue, "Blue spymaster name")
    if exclude_confusing is not None:
        room.exclude_confusing = bool(exclude_confusing)

    _bump(room)
    db.session.commit()
    return room, room.seat_for_player(player_id)


def preview_board(code, player_id):
    room = _get_room_row(code)
    _require_clue_giver(room, player_id)

    if room.status not in (
        CodenamesOnlineRoom.STATUS_WAITING_START,
        CodenamesOnlineRoom.STATUS_PREVIEW,
        CodenamesOnlineRoom.STATUS_WON,
    ):
        raise RoomError("Cannot deal preview right now.", 400)

    if not room.name_red or not room.name_blue:
        raise RoomError("Enter both spymaster names first.", 400)

    _deal_preview(room)
    _bump(room)
    db.session.commit()
    return room, room.seat_for_player(player_id)


def boot_word(code, player_id, index, admin_user_id=None):
    room = _get_room_row(code)
    _require_clue_giver(room, player_id)

    if room.status != CodenamesOnlineRoom.STATUS_PREVIEW:
        raise RoomError("Boot is only available during preview.", 400)

    if index is None or not isinstance(index, int) or index < 0 or index >= BOARD_SIZE:
        raise RoomError("Invalid word index.", 400)

    old_word = room.words[index]
    tag_confusing(old_word, admin_user_id)

    try:
        replacement = pick_replacement_word(
            room.word_list_id,
            room.exclude_confusing,
            room.words,
            index,
        )
    except ValueError as exc:
        raise RoomError(str(exc), 400) from exc

    words = list(room.words)
    words[index] = replacement
    room.words = words
    _bump(room)
    db.session.commit()
    return room, room.seat_for_player(player_id)


def start_game(code, player_id):
    room = _get_room_row(code)
    _require_clue_giver(room, player_id)

    if room.status != CodenamesOnlineRoom.STATUS_PREVIEW:
        raise RoomError("Deal a preview board first.", 400)

    room.status = CodenamesOnlineRoom.STATUS_ACTIVE
    _bump(room)
    db.session.commit()
    return room, room.seat_for_player(player_id)


def guess_word(code, player_id, index):
    room = _get_room_row(code)
    _require_guesser(room, player_id)

    if room.status != CodenamesOnlineRoom.STATUS_ACTIVE:
        raise RoomError("The game is not active.", 400)

    if index is None or not isinstance(index, int) or index < 0 or index >= BOARD_SIZE:
        raise RoomError("Invalid word index.", 400)

    revealed = list(room.revealed or [False] * BOARD_SIZE)
    if revealed[index]:
        return room, room.seat_for_player(player_id)

    revealed[index] = True
    room.revealed = revealed
    apply_guess(room, index)
    _bump(room)
    db.session.commit()
    return room, room.seat_for_player(player_id)


def end_turn(code, player_id):
    room = _get_room_row(code)
    _require_guesser(room, player_id)

    if room.status != CodenamesOnlineRoom.STATUS_ACTIVE:
        raise RoomError("The game is not active.", 400)

    room.turn = "blue" if room.turn == "red" else "red"
    _bump(room)
    db.session.commit()
    return room, room.seat_for_player(player_id)


def rematch(code, player_id):
    room = _get_room_row(code)
    _require_seat(room, player_id)

    if room.status != CodenamesOnlineRoom.STATUS_WON:
        raise RoomError("The game is not over yet.", 400)

    room.words = None
    room.key = None
    room.revealed = None
    room.turn = None
    room.winner = None
    room.status = CodenamesOnlineRoom.STATUS_WAITING_START
    _bump(room)
    db.session.commit()
    return room, room.seat_for_player(player_id)
