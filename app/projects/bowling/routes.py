from flask import Blueprint, render_template

from app.utils.logging import log_project_visit

bowling_bp = Blueprint(
    "bowling",
    __name__,
    url_prefix="/bowling",
    template_folder="templates",
    static_folder="static",
    static_url_path="/bowling/static",
)


@bowling_bp.route("/")
def index():
    log_project_visit("bowling", "Bowling")
    return render_template("bowling/index.html")
