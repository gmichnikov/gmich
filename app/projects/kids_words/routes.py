import json
import os

from flask import Blueprint, jsonify, render_template
from app.utils.logging import log_project_visit

kids_words_bp = Blueprint(
    "kids_words",
    __name__,
    template_folder="templates",
    static_folder="static",
)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


@kids_words_bp.route("/")
def index():
    """Kids Words - placeholder route"""
    log_project_visit("kids_words", "Kids Words")
    return render_template("kids_words/index.html")


@kids_words_bp.route("/api/words/grade2")
def api_grade2():
    """Return grade 2 word list (word -> yes/no)."""
    with open(os.path.join(_DATA_DIR, "grade2_words.json")) as f:
        return jsonify(json.load(f))


@kids_words_bp.route("/api/words/grade4")
def api_grade4():
    """Return grade 4 word list (word -> yes/no)."""
    with open(os.path.join(_DATA_DIR, "grade4_words.json")) as f:
        return jsonify(json.load(f))


@kids_words_bp.route("/api/words/guesses")
def api_guesses():
    """Return valid guess words as JSON array (one per line from wordle_guesses.txt)."""
    path = os.path.join(_DATA_DIR, "wordle_guesses.txt")
    with open(path) as f:
        words = [line.strip().lower() for line in f if line.strip()]
    return jsonify(words)
