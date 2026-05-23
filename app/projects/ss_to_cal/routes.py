from flask import Blueprint, render_template
from flask_login import login_required

from app.utils.logging import log_project_visit

ss_to_cal_bp = Blueprint(
    "ss_to_cal",
    __name__,
    url_prefix="/ss-to-cal",
    template_folder="templates",
    static_folder="static",
    static_url_path="/ss-to-cal/static",
)


@ss_to_cal_bp.route("/")
@login_required
def index():
    log_project_visit("ss_to_cal", "SS to Cal")
    return render_template("ss_to_cal/index.html")
