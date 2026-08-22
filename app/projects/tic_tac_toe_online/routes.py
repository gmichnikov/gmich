import re
import uuid

from flask import Blueprint, jsonify, render_template, request, session

from app.projects.tic_tac_toe_online.room_service import (
    RoomError,
    cleanup_stale_rooms,
    create_room,
    get_state,
    join_room,
    make_move,
    rematch,
    set_name,
    set_symbol,
)
from app.projects.tic_tac_toe_online.serialize import room_to_dict
from app.utils.logging import log_project_visit

tic_tac_toe_online_bp = Blueprint(
    "tic_tac_toe_online",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/tic-tac-toe-online/static",
)

_SESSION_KEY = "ttto_player_id"
_PLAYER_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_PLAYER_HEADER = "X-TTTO-Player-Id"


def _player_id():
    """
    Stable per-browser id for seat identity.

    Prefer the client-supplied header (backed by localStorage) so identity
    survives flaky session cookies. Fall back to the signed session cookie.
    """
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


@tic_tac_toe_online_bp.route("/")
def index():
    """Landing page: create a new room or join one via a code/link."""
    cleanup_stale_rooms()
    log_project_visit("tic_tac_toe_online", "Tic-Tac-Toe Online")
    return render_template("tic_tac_toe_online/index.html")


@tic_tac_toe_online_bp.route("/rooms", methods=["POST"])
@_handle_room_errors
def api_create_room():
    room = create_room()
    return jsonify({"code": room.code}), 201


@tic_tac_toe_online_bp.route("/room/<code>")
def room_page(code):
    """Room page shell. Seats are claimed via POST /join (not here) so bots/prefetchers can't steal them."""
    try:
        room, _seat = get_state(code, _player_id())
    except RoomError as exc:
        return (
            render_template("tic_tac_toe_online/not_found.html", message=exc.message),
            exc.status_code,
        )
    return render_template("tic_tac_toe_online/room.html", code=room.code)


@tic_tac_toe_online_bp.route("/room/<code>/join", methods=["POST"])
@_handle_room_errors
def api_room_join(code):
    data = request.get_json(silent=True) or {}
    room, seat = join_room(code, _player_id(), name=data.get("name"))
    return jsonify(room_to_dict(room, seat))


@tic_tac_toe_online_bp.route("/room/<code>/name", methods=["POST"])
@_handle_room_errors
def api_room_name(code):
    data = request.get_json(silent=True) or {}
    room, seat = set_name(code, _player_id(), data.get("name", ""))
    return jsonify(room_to_dict(room, seat))


@tic_tac_toe_online_bp.route("/room/<code>/symbol", methods=["POST"])
@_handle_room_errors
def api_room_symbol(code):
    data = request.get_json(silent=True) or {}
    room, seat = set_symbol(code, _player_id(), data.get("symbol", ""))
    return jsonify(room_to_dict(room, seat))


@tic_tac_toe_online_bp.route("/room/<code>/state")
@_handle_room_errors
def api_room_state(code):
    room, seat = get_state(code, _player_id())
    return jsonify(room_to_dict(room, seat))


@tic_tac_toe_online_bp.route("/room/<code>/move", methods=["POST"])
@_handle_room_errors
def api_room_move(code):
    data = request.get_json(silent=True) or {}
    room, seat = make_move(code, _player_id(), data.get("cell"))
    return jsonify(room_to_dict(room, seat))


@tic_tac_toe_online_bp.route("/room/<code>/rematch", methods=["POST"])
@_handle_room_errors
def api_room_rematch(code):
    room, seat = rematch(code, _player_id())
    return jsonify(room_to_dict(room, seat))
