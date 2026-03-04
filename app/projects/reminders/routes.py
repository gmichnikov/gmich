from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.utils.logging import log_project_visit

reminders_bp = Blueprint(
    "reminders",
    __name__,
    url_prefix="/reminders",
    template_folder="templates",
    static_folder="static",
    static_url_path="/reminders/static",
)


@reminders_bp.route("/")
@login_required
def index():
    """Main page: list of reminders."""
    log_project_visit("reminders", "Reminders")
    return render_template("reminders/index.html", reminders=[])
