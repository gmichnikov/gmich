import re
import uuid

from flask import Blueprint, jsonify, render_template, request, session

from app.projects.friend_wordle.room_service import (
    RoomError,
    claim_setter,
    cleanup_stale_rooms,
    confirm_secret,
    create_room,
    get_state,
    join_room,
    rematch,
    set_name,
    set_secret,
    submit_guess,
)
from app.projects.friend_wordle.serialize import room_to_dict
from app.utils.logging import log_project_visit
from app.utils.wordle.word_lists import load_valid_guesses

friend_wordle_bp = Blueprint(
    "friend_wordle",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/friend-wordle-online/static",
)

_SESSION_KEY = "fw_player_id"
_PLAYER_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_PLAYER_HEADER = "X-FW-Player-Id"


def _player_id():
    header_id = (request.headers.get(_PLAYER_HEADER) or "").strip().lower()
    if _PLAYER_ID_RE.fullmatch(header_id):
        session[_SESSION_KEY] = header_id
        return header_id

    player_id = session.get(_SESSION_KEY)
    if not player_id or not _PLAYER_ID_RE.fullmatch(str(player_id)):
        player_id = uuid.uuid4().hex
        session[_SESSION_KEY] = player_id
    return player_id


def _handle_room_errors(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except RoomError as exc:
            return jsonify({"error": exc.message}), exc.status_code

    wrapper.__name__ = fn.__name__
    return wrapper


@friend_wordle_bp.route("/")
def index():
    cleanup_stale_rooms()
    log_project_visit("friend_wordle", "Friend Wordle")
    return render_template("friend_wordle/index.html")


@friend_wordle_bp.route("/api/guesses")
def api_guesses():
    return jsonify(sorted(load_valid_guesses()))


@friend_wordle_bp.route("/rooms", methods=["POST"])
@_handle_room_errors
def api_create_room():
    room = create_room(_player_id())
    return jsonify({"code": room.code}), 201


@friend_wordle_bp.route("/room/<code>")
def room_page(code):
    try:
        room, _seat = get_state(code, _player_id())
    except RoomError as exc:
        return (
            render_template("friend_wordle/not_found.html", message=exc.message),
            exc.status_code,
        )
    return render_template("friend_wordle/room.html", code=room.code)


@friend_wordle_bp.route("/room/<code>/join", methods=["POST"])
@_handle_room_errors
def api_room_join(code):
    data = request.get_json(silent=True) or {}
    room, seat = join_room(code, _player_id(), name=data.get("name"))
    return jsonify(room_to_dict(room, seat))


@friend_wordle_bp.route("/room/<code>/name", methods=["POST"])
@_handle_room_errors
def api_room_name(code):
    data = request.get_json(silent=True) or {}
    room, seat = set_name(code, _player_id(), data.get("name", ""))
    return jsonify(room_to_dict(room, seat))


@friend_wordle_bp.route("/room/<code>/claim-setter", methods=["POST"])
@_handle_room_errors
def api_room_claim_setter(code):
    room, seat = claim_setter(code, _player_id())
    return jsonify(room_to_dict(room, seat))


@friend_wordle_bp.route("/room/<code>/secret", methods=["POST"])
@_handle_room_errors
def api_room_secret(code):
    data = request.get_json(silent=True) or {}
    room, seat = set_secret(code, _player_id(), data.get("word", ""))
    return jsonify(room_to_dict(room, seat))


@friend_wordle_bp.route("/room/<code>/confirm", methods=["POST"])
@_handle_room_errors
def api_room_confirm(code):
    room, seat = confirm_secret(code, _player_id())
    return jsonify(room_to_dict(room, seat))


@friend_wordle_bp.route("/room/<code>/state")
@_handle_room_errors
def api_room_state(code):
    room, seat = get_state(code, _player_id())
    return jsonify(room_to_dict(room, seat))


@friend_wordle_bp.route("/room/<code>/guess", methods=["POST"])
@_handle_room_errors
def api_room_guess(code):
    data = request.get_json(silent=True) or {}
    room, seat = submit_guess(code, _player_id(), data.get("word", ""))
    return jsonify(room_to_dict(room, seat))


@friend_wordle_bp.route("/room/<code>/rematch", methods=["POST"])
@_handle_room_errors
def api_room_rematch(code):
    room, seat = rematch(code, _player_id())
    return jsonify(room_to_dict(room, seat))
