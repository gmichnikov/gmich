from flask import Blueprint, render_template

from app.utils.logging import log_project_visit

sports_scores_bp = Blueprint(
    "sports_scores",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/sports-scores/static",
    url_prefix="/sports-scores",
)


@sports_scores_bp.route("/")
def index():
    log_project_visit("sports_scores", "Sports Scores")
    return render_template("sports_scores/index.html")
