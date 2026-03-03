import json
import os

from flask import Blueprint, jsonify, render_template
from flask_login import current_user
from app import db
from app.models import LogEntry
from app.utils.logging import log_project_visit

kids_words_bp = Blueprint(
    "kids_words",
    __name__,
    template_folder="templates",
    static_folder="static",
)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load_json(path):
    """Load JSON file, return None if not found."""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def _load_guesses():
    """Load guess words, return empty list if not found."""
    try:
        path = os.path.join(_DATA_DIR, "wordle_guesses.txt")
        with open(path) as f:
            return [line.strip().lower() for line in f if line.strip()]
    except FileNotFoundError:
        return []


@kids_words_bp.route("/")
def index():
    """Kids Words - placeholder route"""
    log_project_visit("kids_words", "Kids Words")
    return render_template("kids_words/index.html")


@kids_words_bp.route("/api/words/grade2")
def api_grade2():
    """Return grade 2 word list (word -> yes/no)."""
    data = _load_json(os.path.join(_DATA_DIR, "grade2_words.json"))
    if data is None:
        return jsonify({"error": "Grade 2 words not found"}), 404
    return jsonify(data)


@kids_words_bp.route("/api/words/grade4")
def api_grade4():
    """Return grade 4 word list (word -> yes/no)."""
    data = _load_json(os.path.join(_DATA_DIR, "grade4_words.json"))
    if data is None:
        return jsonify({"error": "Grade 4 words not found"}), 404
    return jsonify(data)


@kids_words_bp.route("/api/words/guesses")
def api_guesses():
    """Return valid guess words as JSON array (one per line from wordle_guesses.txt)."""
    words = _load_guesses()
    return jsonify(words)


@kids_words_bp.route("/api/log/new-game", methods=["POST"])
def log_new_game():
    """Called by the client when a new game starts."""
    db.session.add(LogEntry(
        actor_id=current_user.id if current_user.is_authenticated else None,
        project="kids_words",
        category="New Game",
        description="Started a new Kids Words game",
    ))
    db.session.commit()
    return jsonify({"ok": True})
