from flask import Blueprint, render_template
from flask_login import login_required

from app.utils.logging import log_project_visit

soccer_minutes_bp = Blueprint(
    "soccer_minutes",
    __name__,
    url_prefix="/soccer-minutes",
    template_folder="templates",
    static_folder="static",
    static_url_path="/soccer-minutes/static",
)


@soccer_minutes_bp.route("/")
@login_required
def index():
    log_project_visit("soccer_minutes", "Soccer Minutes")
    return render_template("soccer_minutes/index.html")
