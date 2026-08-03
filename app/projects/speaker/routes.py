import os

from flask import Blueprint, jsonify, render_template

from app.utils.logging import log_project_visit

speaker_bp = Blueprint(
    "speaker",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/speaker/static",
)

_COMMON_WORDS_PATH = os.path.join(os.path.dirname(__file__), "common.txt")
_common_words_cache = None


def _load_common_words():
    """Load frequency-ordered words from common.txt, deduped (first wins)."""
    global _common_words_cache
    if _common_words_cache is not None:
        return _common_words_cache

    seen = set()
    words = []
    try:
        with open(_COMMON_WORDS_PATH, encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if not word:
                    continue
                key = word.lower()
                if key in seen:
                    continue
                seen.add(key)
                words.append(word)
    except FileNotFoundError:
        words = []

    _common_words_cache = words
    return words


@speaker_bp.route("/")
def index():
    """Speaker — client-side AAC board, no login or database."""
    log_project_visit("speaker", "Speaker")
    return render_template("speaker/index.html")


@speaker_bp.route("/api/words/common")
def api_common_words():
    """Return deduped common-word list for spell-keyboard autocomplete."""
    return jsonify(_load_common_words())
