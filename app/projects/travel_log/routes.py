from flask import Blueprint, render_template
from flask_login import login_required

from app.utils.logging import log_project_visit

travel_log_bp = Blueprint(
    "travel_log",
    __name__,
    url_prefix="/travel-log",
    template_folder="templates",
    static_folder="static",
    static_url_path="/travel-log/static",
)


@travel_log_bp.route("/")
@login_required
def index():
    log_project_visit("travel_log", "Travel Log")
    return render_template("travel_log/index.html")
