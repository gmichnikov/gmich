from flask import Blueprint, render_template
from flask_login import login_required

from app.utils.logging import log_project_visit

daily_email_bp = Blueprint(
    "daily_email",
    __name__,
    url_prefix="/daily-email",
    template_folder="templates",
    static_folder="static",
    static_url_path="/daily-email/static",
)


@daily_email_bp.route("/")
@login_required
def index():
    log_project_visit("daily_email", "Daily Email")
    return render_template("daily_email/index.html")
