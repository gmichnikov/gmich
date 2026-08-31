import re
import uuid

from flask import Blueprint, jsonify, render_template, request, session

from app.projects.battleship_online.room_service import (
    RoomError,
    adjust_ship,
    cleanup_stale_rooms,
    create_cpu_room,
    create_room,
    fire,
    get_state,
    join_room,
    rematch,
    set_name,
    set_ready,
    set_unready,
    shuffle_fleet,
)
from app.projects.battleship_online.serialize import room_to_dict
from app.utils.logging import log_project_visit

battleship_online_bp = Blueprint(
    "battleship_online",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/battleship-online/static",
)

_SESSION_KEY = "bso_player_id"
_PLAYER_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_PLAYER_HEADER = "X-BSO-Player-Id"


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


@battleship_online_bp.route("/")
def index():
    cleanup_stale_rooms()
    log_project_visit("battleship_online", "Battleship Online")
    return render_template("battleship_online/index.html")


@battleship_online_bp.route("/rooms", methods=["POST"])
@_handle_room_errors
def api_create_room():
    data = request.get_json(silent=True) or {}
    if data.get("vs_cpu"):
        room = create_cpu_room()
    else:
        room = create_room()
    return jsonify({"code": room.code}), 201


@battleship_online_bp.route("/room/<code>")
def room_page(code):
    try:
        room, _seat = get_state(code, _player_id())
    except RoomError as exc:
        return (
            render_template("battleship_online/not_found.html", message=exc.message),
            exc.status_code,
        )
    return render_template("battleship_online/room.html", code=room.code)


@battleship_online_bp.route("/room/<code>/join", methods=["POST"])
@_handle_room_errors
def api_room_join(code):
    data = request.get_json(silent=True) or {}
    room, seat = join_room(code, _player_id(), name=data.get("name"))
    return jsonify(room_to_dict(room, seat))


@battleship_online_bp.route("/room/<code>/name", methods=["POST"])
@_handle_room_errors
def api_room_name(code):
    data = request.get_json(silent=True) or {}
    room, seat = set_name(code, _player_id(), data.get("name", ""))
    return jsonify(room_to_dict(room, seat))


@battleship_online_bp.route("/room/<code>/shuffle", methods=["POST"])
@_handle_room_errors
def api_room_shuffle(code):
    room, seat = shuffle_fleet(code, _player_id())
    return jsonify(room_to_dict(room, seat))


@battleship_online_bp.route("/room/<code>/ship", methods=["POST"])
@_handle_room_errors
def api_room_ship(code):
    data = request.get_json(silent=True) or {}
    room, seat = adjust_ship(
        code,
        _player_id(),
        data.get("ship_index"),
        data.get("action"),
    )
    return jsonify(room_to_dict(room, seat))


@battleship_online_bp.route("/room/<code>/ready", methods=["POST"])
@_handle_room_errors
def api_room_ready(code):
    room, seat = set_ready(code, _player_id())
    return jsonify(room_to_dict(room, seat))


@battleship_online_bp.route("/room/<code>/unready", methods=["POST"])
@_handle_room_errors
def api_room_unready(code):
    room, seat = set_unready(code, _player_id())
    return jsonify(room_to_dict(room, seat))


@battleship_online_bp.route("/room/<code>/state")
@_handle_room_errors
def api_room_state(code):
    room, seat = get_state(code, _player_id())
    return jsonify(room_to_dict(room, seat))


@battleship_online_bp.route("/room/<code>/fire", methods=["POST"])
@_handle_room_errors
def api_room_fire(code):
    data = request.get_json(silent=True) or {}
    room, seat, event = fire(code, _player_id(), data.get("row"), data.get("col"))
    payload = room_to_dict(room, seat)
    if event:
        payload["event"] = event
    return jsonify(payload)


@battleship_online_bp.route("/room/<code>/rematch", methods=["POST"])
@_handle_room_errors
def api_room_rematch(code):
    room, seat = rematch(code, _player_id())
    return jsonify(room_to_dict(room, seat))
