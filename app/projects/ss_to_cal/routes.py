import os
import time

from flask import Blueprint, current_app, render_template, request, send_from_directory
from flask_login import current_user, login_required

from app import csrf
from app.projects.ss_to_cal.extraction import (
    ExtractionApiError,
    ExtractionParseError,
    count_fields_populated,
    extract_event_from_image,
    is_no_event_found,
    normalize_extraction,
)
from app.projects.ss_to_cal.image_utils import ImageProcessingError, prepare_image_for_api
from app.projects.ss_to_cal.logging_utils import log_share_extraction, log_share_not_logged_in
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

    started = time.monotonic()
    actor_id = current_user.id

    image_file, image_error = _read_shared_image()
    if image_error:
        return _render_share(
            extraction=EMPTY_EXTRACTION,
            error_message=image_error,
            started=started,
            actor_id=actor_id,
            outcome="image_error",
            error_code="IMAGE_INVALID",
        )

    try:
        jpeg_bytes, image_width, image_height = prepare_image_for_api(image_file)
    except ImageProcessingError as exc:
        return _render_share(
            extraction=EMPTY_EXTRACTION,
            error_message=str(exc),
            started=started,
            actor_id=actor_id,
            outcome="image_error",
            error_code="IMAGE_INVALID",
        )
    finally:
        image_file.close()

    try:
        parsed, api_meta = extract_event_from_image(
            jpeg_bytes,
            distinct_id=str(actor_id),
        )
    except ExtractionApiError as exc:
        current_app.logger.error("SS to Cal extraction API error: %s", exc)
        user_message = (
            "Vision extraction is unavailable right now. Please try again in a moment."
            if "API_KEY" in str(exc)
            else "Could not analyze the screenshot. Please try sharing it again."
        )
        return _render_share(
            extraction=EMPTY_EXTRACTION,
            error_message=user_message,
            started=started,
            actor_id=actor_id,
            outcome="api_error",
            error_code="API_ERROR",
            image_width=image_width,
            image_height=image_height,
        )
    except ExtractionParseError:
        current_app.logger.exception("SS to Cal extraction parse failed")
        return _render_share(
            extraction=EMPTY_EXTRACTION,
            error_message="Could not read the extraction result. Please try sharing the screenshot again.",
            started=started,
            actor_id=actor_id,
            outcome="parse_failed",
            error_code="PARSE_FAILED",
            image_width=image_width,
            image_height=image_height,
        )
    except TimeoutError:
        current_app.logger.error("SS to Cal extraction timed out")
        return _render_share(
            extraction=EMPTY_EXTRACTION,
            error_message="Extraction took too long. Please try again on a stronger connection.",
            started=started,
            actor_id=actor_id,
            outcome="timeout",
            error_code="API_ERROR",
            image_width=image_width,
            image_height=image_height,
        )
    except Exception:
        current_app.logger.exception("SS to Cal extraction failed")
        return _render_share(
            extraction=EMPTY_EXTRACTION,
            error_message="Could not analyze the screenshot. Please try sharing it again.",
            started=started,
            actor_id=actor_id,
            outcome="api_error",
            error_code="API_ERROR",
            image_width=image_width,
            image_height=image_height,
        )
    finally:
        del jpeg_bytes

    if is_no_event_found(parsed):
        return _render_share(
            extraction=EMPTY_EXTRACTION,
            info_message="No event details were found in that image. Fill in the fields below or share a different screenshot.",
            started=started,
            actor_id=actor_id,
            outcome="no_event_found",
            error_code="NO_EVENT_FOUND",
            api_meta=api_meta,
            image_width=image_width,
            image_height=image_height,
        )

    extraction = normalize_extraction(parsed)
    return _render_share(
        extraction=extraction,
        started=started,
        actor_id=actor_id,
        outcome="success",
        api_meta=api_meta,
        image_width=image_width,
        image_height=image_height,
    )


def _render_share(
    *,
    extraction,
    started,
    actor_id,
    outcome,
    error_message=None,
    info_message=None,
    error_code=None,
    api_meta=None,
    image_width=None,
    image_height=None,
):
    latency_ms = int((time.monotonic() - started) * 1000)
    api_meta = api_meta or {}

    log_share_extraction(
        actor_id=actor_id,
        outcome=outcome,
        latency_ms=latency_ms,
        model=api_meta.get("model"),
        input_tokens=api_meta.get("input_tokens", 0),
        output_tokens=api_meta.get("output_tokens", 0),
        confidence=extraction.get("confidence"),
        fields_populated=count_fields_populated(extraction),
        image_width=image_width,
        image_height=image_height,
        error_code=error_code,
        api_latency_ms=api_meta.get("api_latency_ms"),
    )

    return (
        render_template(
            "ss_to_cal/share.html",
            extraction=extraction,
            error_message=error_message,
            info_message=info_message,
        ),
        200,
    )


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
