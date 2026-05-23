import os

from flask import Blueprint, render_template, request, send_from_directory
from flask_login import current_user, login_required

from app import csrf
from app.projects.ss_to_cal.logging_utils import log_share_not_logged_in
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
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

EMPTY_EXTRACTION = {
    "title": None,
    "date": None,
    "startTime": None,
    "endTime": None,
    "location": None,
    "description": None,
    "timezone": None,
    "confidence": None,
}


@ss_to_cal_bp.route("/")
@login_required
def index():
    log_project_visit("ss_to_cal", "SS to Cal")
    return render_template("ss_to_cal/index.html")


@ss_to_cal_bp.route("/share", methods=["POST"])
@csrf.exempt
def share():
    if not current_user.is_authenticated:
        log_share_not_logged_in()
        return render_template("ss_to_cal/share_login.html"), 200

    image_file, image_error = _read_shared_image()
    if image_error:
        return render_template(
            "ss_to_cal/share.html",
            extraction=EMPTY_EXTRACTION,
            image_received=False,
            error_message=image_error,
        ), 200

    # Phase 2 stub: image validated in memory only; not stored or sent to LLM.
    del image_file

    return render_template(
        "ss_to_cal/share.html",
        extraction=EMPTY_EXTRACTION,
        image_received=True,
        error_message=None,
    ), 200


def _read_shared_image():
    """Return (file, error_message). Exactly one of the tuple values is set."""
    image_file = request.files.get("image")
    if not image_file or not image_file.filename:
        return None, "No image was shared. Try sharing a screenshot again."

    image_file.seek(0, os.SEEK_END)
    size = image_file.tell()
    image_file.seek(0)

    if size == 0:
        return None, "The shared image was empty. Try sharing a screenshot again."

    if size > MAX_UPLOAD_BYTES:
        return None, "That image is too large. Try sharing a smaller screenshot."

    mime = (image_file.mimetype or "").lower()
    if mime and not mime.startswith("image/"):
        return None, "Shared file must be an image. Try sharing a screenshot again."

    return image_file, None


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
