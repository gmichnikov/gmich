import re
import uuid

from flask import Blueprint, jsonify, render_template, request, session

from app.projects.connect4_online.room_service import (
    RoomError,
    cleanup_stale_rooms,
    create_room,
    get_state,
    join_room,
    make_move,
    rematch,
    set_color,
    set_name,
)
from app.projects.connect4_online.serialize import room_to_dict
from app.utils.logging import log_project_visit

connect4_online_bp = Blueprint(
    "connect4_online",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/connect4-online/static",
)

_SESSION_KEY = "c4o_player_id"
_PLAYER_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_PLAYER_HEADER = "X-C4O-Player-Id"


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


@connect4_online_bp.route("/")
def index():
    cleanup_stale_rooms()
    log_project_visit("connect4_online", "Connect 4 Online")
    return render_template("connect4_online/index.html")


@connect4_online_bp.route("/rooms", methods=["POST"])
@_handle_room_errors
def api_create_room():
    room = create_room()
    return jsonify({"code": room.code}), 201


@connect4_online_bp.route("/room/<code>")
def room_page(code):
    try:
        room, _seat = get_state(code, _player_id())
    except RoomError as exc:
        return (
            render_template("connect4_online/not_found.html", message=exc.message),
            exc.status_code,
        )
    return render_template("connect4_online/room.html", code=room.code)


@connect4_online_bp.route("/room/<code>/join", methods=["POST"])
@_handle_room_errors
def api_room_join(code):
    data = request.get_json(silent=True) or {}
    room, seat = join_room(code, _player_id(), name=data.get("name"))
    return jsonify(room_to_dict(room, seat))


@connect4_online_bp.route("/room/<code>/name", methods=["POST"])
@_handle_room_errors
def api_room_name(code):
    data = request.get_json(silent=True) or {}
    room, seat = set_name(code, _player_id(), data.get("name", ""))
    return jsonify(room_to_dict(room, seat))


@connect4_online_bp.route("/room/<code>/color", methods=["POST"])
@_handle_room_errors
def api_room_color(code):
    data = request.get_json(silent=True) or {}
    room, seat = set_color(code, _player_id(), data.get("color", ""))
    return jsonify(room_to_dict(room, seat))


@connect4_online_bp.route("/room/<code>/state")
@_handle_room_errors
def api_room_state(code):
    room, seat = get_state(code, _player_id())
    return jsonify(room_to_dict(room, seat))


@connect4_online_bp.route("/room/<code>/move", methods=["POST"])
@_handle_room_errors
def api_room_move(code):
    data = request.get_json(silent=True) or {}
    room, seat = make_move(code, _player_id(), data.get("col"))
    return jsonify(room_to_dict(room, seat))


@connect4_online_bp.route("/room/<code>/rematch", methods=["POST"])
@_handle_room_errors
def api_room_rematch(code):
    room, seat = rematch(code, _player_id())
    return jsonify(room_to_dict(room, seat))
