import logging

from flask import Blueprint, jsonify, render_template

from app.projects.election2026.service import board_payload, refresh_if_stale
from app.utils.logging import log_project_visit

logger = logging.getLogger(__name__)

election2026_bp = Blueprint(
    "election2026",
    __name__,
    url_prefix="/election-2026",
    template_folder="templates",
    static_folder="static",
    static_url_path="/election-2026/static",
)


@election2026_bp.route("/")
def index():
    """Public board. No login."""
    log_project_visit("election2026", "Election 2026")
    return render_template("election2026/index.html")


@election2026_bp.route("/api/board")
def api_board():
    """Current charts. Talks to Kalshi only when the saved prices are a minute old."""
    try:
        refresh = refresh_if_stale()
    except Exception:
        logger.exception("Election board refresh failed")
        refresh = {"pulled": False, "errors": ["Kalshi could not be reached."]}
    payload = board_payload()
    payload.update(refresh)
    return jsonify(payload)
