from flask import Blueprint, render_template

from app.utils.logging import log_project_visit

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
    """Public board. No login. Prices are not collected yet."""
    log_project_visit("election2026", "Election 2026")
    return render_template("election2026/index.html")
