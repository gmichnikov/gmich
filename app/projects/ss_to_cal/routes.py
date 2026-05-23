import os

from flask import Blueprint, render_template, send_from_directory
from flask_login import login_required

from app.utils.logging import log_project_visit

ss_to_cal_bp = Blueprint(
    "ss_to_cal",
    __name__,
    url_prefix="/ss-to-cal",
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@ss_to_cal_bp.route("/")
@login_required
def index():
    log_project_visit("ss_to_cal", "SS to Cal")
    return render_template("ss_to_cal/index.html")


@ss_to_cal_bp.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(
        _STATIC_DIR,
        "manifest.webmanifest",
        mimetype="application/manifest+json",
    )


@ss_to_cal_bp.route("/sw.js")
def service_worker():
    response = send_from_directory(_STATIC_DIR, "sw.js", mimetype="application/javascript")
    response.headers["Cache-Control"] = "no-cache"
    return response
