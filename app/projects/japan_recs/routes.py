from flask import Blueprint, render_template

from app.utils.logging import log_project_visit

japan_recs_bp = Blueprint(
    "japan_recs",
    __name__,
    url_prefix="/japan-recs",
    template_folder="templates",
    static_folder="static",
    static_url_path="/japan-recs/static",
)


@japan_recs_bp.route("/")
def index():
    """Japan Recs — public recommendations page, no login or database."""
    log_project_visit("japan_recs", "Japan Recs")
    return render_template("japan_recs/index.html")
