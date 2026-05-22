import re

from flask import Blueprint, jsonify, render_template, request, url_for

from app import db
from app.projects.bowling.game_service import (
    BowlingApiError,
    add_player,
    clear_frame,
    create_game,
    get_game_by_code,
    mark_complete,
    remove_player,
    reorder_players,
    start_game,
    submit_roll,
    update_player_name,
)
from app.projects.bowling.models import BowlingGame
from app.projects.bowling.serialize import game_to_dict
from app.utils.logging import log_project_visit

bowling_bp = Blueprint(
    "bowling",
    __name__,
    url_prefix="/bowling",
    template_folder="templates",
    static_folder="static",
    static_url_path="/bowling/static",
)

_CODE_PATTERN = re.compile(r"^\d{6}$")


def _json_error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


def _handle_api_errors(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except BowlingApiError as exc:
            return _json_error(exc.message, exc.status_code)

    wrapper.__name__ = fn.__name__
    return wrapper


def _game_response(code: str):
    db.session.expire_all()
    game = get_game_by_code(code)
    return jsonify(game_to_dict(game))


@bowling_bp.route("/")
def index():
    log_project_visit("bowling", "Bowling")
    return render_template("bowling/index.html")


@bowling_bp.route("/<code>")
def game_page(code):
    if not _CODE_PATTERN.fullmatch(code):
        return render_template("bowling/not_found.html"), 404
    game = BowlingGame.query.filter_by(code=code).first()
    if not game:
        return render_template("bowling/not_found.html"), 404
    return render_template("bowling/game.html", code=code)


@bowling_bp.route("/api/games", methods=["POST"])
@_handle_api_errors
def api_create_game():
    game = create_game()
    return (
        jsonify(
            {
                "code": game.code,
                "url": url_for("bowling.game_page", code=game.code, _external=False),
            }
        ),
        201,
    )


@bowling_bp.route("/api/games/<code>", methods=["GET"])
@_handle_api_errors
def api_get_game(code):
    if not _CODE_PATTERN.fullmatch(code):
        raise BowlingApiError("No game found with that code.", 404)
    return _game_response(code)


@bowling_bp.route("/api/games/<code>/players", methods=["POST"])
@_handle_api_errors
def api_add_player(code):
    if not _CODE_PATTERN.fullmatch(code):
        raise BowlingApiError("No game found with that code.", 404)
    game = get_game_by_code(code)
    data = request.get_json(silent=True) or {}
    add_player(game, data.get("name", ""))
    return _game_response(code)


@bowling_bp.route("/api/games/<code>/players/<int:player_id>", methods=["PUT"])
@_handle_api_errors
def api_update_player(code, player_id):
    if not _CODE_PATTERN.fullmatch(code):
        raise BowlingApiError("No game found with that code.", 404)
    game = get_game_by_code(code)
    data = request.get_json(silent=True) or {}
    update_player_name(game, player_id, data.get("name", ""))
    return _game_response(code)


@bowling_bp.route("/api/games/<code>/players/<int:player_id>", methods=["DELETE"])
@_handle_api_errors
def api_remove_player(code, player_id):
    if not _CODE_PATTERN.fullmatch(code):
        raise BowlingApiError("No game found with that code.", 404)
    game = get_game_by_code(code)
    remove_player(game, player_id)
    return _game_response(code)


@bowling_bp.route("/api/games/<code>/players/order", methods=["PUT"])
@_handle_api_errors
def api_reorder_players(code):
    if not _CODE_PATTERN.fullmatch(code):
        raise BowlingApiError("No game found with that code.", 404)
    game = get_game_by_code(code)
    data = request.get_json(silent=True) or {}
    reorder_players(game, data.get("player_ids"))
    return _game_response(code)


@bowling_bp.route("/api/games/<code>/start", methods=["POST"])
@_handle_api_errors
def api_start_game(code):
    if not _CODE_PATTERN.fullmatch(code):
        raise BowlingApiError("No game found with that code.", 404)
    game = get_game_by_code(code)
    start_game(game)
    return _game_response(code)


@bowling_bp.route("/api/games/<code>/rolls", methods=["POST"])
@_handle_api_errors
def api_submit_roll(code):
    if not _CODE_PATTERN.fullmatch(code):
        raise BowlingApiError("No game found with that code.", 404)
    game = get_game_by_code(code)
    data = request.get_json(silent=True) or {}

    if "player_id" not in data or "frame" not in data or "roll" not in data or "pins" not in data:
        raise BowlingApiError("player_id, frame, roll, and pins are required.")

    submit_roll(
        game,
        int(data["player_id"]),
        int(data["frame"]),
        int(data["roll"]),
        int(data["pins"]),
    )
    return _game_response(code)


@bowling_bp.route("/api/games/<code>/clear", methods=["POST"])
@_handle_api_errors
def api_clear_frame(code):
    if not _CODE_PATTERN.fullmatch(code):
        raise BowlingApiError("No game found with that code.", 404)
    game = get_game_by_code(code)
    data = request.get_json(silent=True) or {}

    if "player_id" not in data or "frame" not in data:
        raise BowlingApiError("player_id and frame are required.")

    clear_frame(game, int(data["player_id"]), int(data["frame"]))
    return _game_response(code)


@bowling_bp.route("/api/games/<code>/complete", methods=["POST"])
@_handle_api_errors
def api_mark_complete(code):
    if not _CODE_PATTERN.fullmatch(code):
        raise BowlingApiError("No game found with that code.", 404)
    game = get_game_by_code(code)
    mark_complete(game)
    return _game_response(code)
