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
    """Japan Recs hub — links to city maps."""
    log_project_visit("japan_recs", "Japan Recs")
    return render_template("japan_recs/index.html")


@japan_recs_bp.route("/kyoto")
def kyoto():
    """Kyoto trip map — public, no login or database."""
    log_project_visit("japan_recs", "Kyoto Map")
    return render_template("japan_recs/kyoto.html")


@japan_recs_bp.route("/tokyo")
def tokyo():
    """Tokyo trip map — public, no login or database."""
    log_project_visit("japan_recs", "Tokyo Map")
    return render_template("japan_recs/tokyo.html")
