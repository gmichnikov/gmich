from flask import Blueprint, render_template
from flask_login import login_required
from app.utils.logging import log_project_visit

helper_bp = Blueprint(
    "helper",
    __name__,
    url_prefix="/helper",
    template_folder="templates",
    static_folder="static",
    static_url_path="/helper/static",
)


@helper_bp.route("/")
@login_required
def index():
    log_project_visit("helper", "Helper")
    return render_template("helper/index.html")
