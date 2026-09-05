import re
import uuid
from functools import wraps

from flask import Blueprint, jsonify, render_template, request, session
from flask_login import current_user, login_required

from app.projects.codenames_online.confusing_words import (
    all_words_catalog,
    tag_confusing,
    untag_confusing,
)
from app.projects.codenames_online.room_service import (
    RoomError,
    boot_word,
    claim_role,
    cleanup_stale_rooms,
    create_room,
    end_turn,
    get_state,
    guess_word,
    join_room,
    preview_board,
    rematch,
    setup_room,
    start_game,
)
from app.projects.codenames_online.serialize import room_to_dict
from app.utils.logging import log_project_visit

codenames_online_bp = Blueprint(
    "codenames_online",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/codenames-online/static",
)

_SESSION_KEY = "cno_player_id"
_PLAYER_ID_RE = re.compile(r"^[a-f0-9]{32}$")
_PLAYER_HEADER = "X-CNO-Player-Id"


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


def _is_admin():
    return current_user.is_authenticated and getattr(current_user, "is_admin", False)


def _serialize(room, seat):
    return room_to_dict(room, seat, is_admin=_is_admin())


def _handle_room_errors(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except RoomError as exc:
            return jsonify({"error": exc.message}), exc.status_code

    wrapper.__name__ = fn.__name__
    return wrapper


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({"error": "Admin access required."}), 403
        return view(*args, **kwargs)

    return wrapped


@codenames_online_bp.route("/")
def index():
    cleanup_stale_rooms()
    log_project_visit("codenames_online", "Codenames")
    return render_template("codenames_online/index.html")


@codenames_online_bp.route("/rooms", methods=["POST"])
@_handle_room_errors
def api_create_room():
    room = create_room(_player_id())
    return jsonify({"code": room.code}), 201


@codenames_online_bp.route("/room/<code>")
def room_page(code):
    try:
        room, _seat = get_state(code, _player_id())
    except RoomError as exc:
        return (
            render_template("codenames_online/not_found.html", message=exc.message),
            exc.status_code,
        )
    return render_template(
        "codenames_online/room.html",
        code=room.code,
        is_admin=_is_admin(),
    )


@codenames_online_bp.route("/room/<code>/join", methods=["POST"])
@_handle_room_errors
def api_room_join(code):
    room, seat = join_room(code, _player_id())
    return jsonify(_serialize(room, seat))


@codenames_online_bp.route("/room/<code>/claim_role", methods=["POST"])
@_handle_room_errors
def api_room_claim_role(code):
    data = request.get_json(silent=True) or {}
    room, seat = claim_role(
        code,
        _player_id(),
        role=data.get("role"),
        swap=bool(data.get("swap")),
    )
    return jsonify(_serialize(room, seat))


@codenames_online_bp.route("/room/<code>/setup", methods=["POST"])
@_handle_room_errors
def api_room_setup(code):
    data = request.get_json(silent=True) or {}
    room, seat = setup_room(
        code,
        _player_id(),
        word_list_id=data.get("word_list_id"),
        name_red=data.get("name_red"),
        name_blue=data.get("name_blue"),
        exclude_confusing=data.get("exclude_confusing"),
    )
    return jsonify(_serialize(room, seat))


@codenames_online_bp.route("/room/<code>/preview", methods=["POST"])
@_handle_room_errors
def api_room_preview(code):
    room, seat = preview_board(code, _player_id())
    return jsonify(_serialize(room, seat))


@codenames_online_bp.route("/room/<code>/boot_word", methods=["POST"])
@_handle_room_errors
def api_room_boot_word(code):
    if not _is_admin():
        return jsonify({"error": "Admin access required."}), 403
    data = request.get_json(silent=True) or {}
    admin_user_id = current_user.id if current_user.is_authenticated else None
    room, seat = boot_word(code, _player_id(), data.get("index"), admin_user_id)
    return jsonify(_serialize(room, seat))


@codenames_online_bp.route("/room/<code>/start", methods=["POST"])
@_handle_room_errors
def api_room_start(code):
    room, seat = start_game(code, _player_id())
    return jsonify(_serialize(room, seat))


@codenames_online_bp.route("/room/<code>/state")
@_handle_room_errors
def api_room_state(code):
    room, seat = get_state(code, _player_id())
    return jsonify(_serialize(room, seat))


@codenames_online_bp.route("/room/<code>/guess", methods=["POST"])
@_handle_room_errors
def api_room_guess(code):
    data = request.get_json(silent=True) or {}
    room, seat = guess_word(code, _player_id(), data.get("index"))
    return jsonify(_serialize(room, seat))


@codenames_online_bp.route("/room/<code>/end_turn", methods=["POST"])
@_handle_room_errors
def api_room_end_turn(code):
    room, seat = end_turn(code, _player_id())
    return jsonify(_serialize(room, seat))


@codenames_online_bp.route("/room/<code>/rematch", methods=["POST"])
@_handle_room_errors
def api_room_rematch(code):
    room, seat = rematch(code, _player_id())
    return jsonify(_serialize(room, seat))


@codenames_online_bp.route("/admin/confusing-words")
@login_required
def admin_confusing_words_page():
    if not current_user.is_admin:
        return render_template("codenames_online/not_found.html", message="Admin access required."), 403
    return render_template("codenames_online/admin_confusing_words.html")


@codenames_online_bp.route("/admin/confusing-words/data")
@admin_required
def admin_confusing_words_data():
    return jsonify({"words": all_words_catalog()})


@codenames_online_bp.route("/admin/confusing-words", methods=["POST"])
@admin_required
def admin_confusing_words_update():
    data = request.get_json(silent=True) or {}
    word = data.get("word")
    confusing = data.get("confusing")
    if confusing:
        tag_confusing(word, current_user.id)
    else:
        untag_confusing(word)
    return jsonify({"ok": True})
