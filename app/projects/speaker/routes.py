from flask import Blueprint, render_template

from app.utils.logging import log_project_visit

speaker_bp = Blueprint(
    "speaker",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/speaker/static",
)


@speaker_bp.route("/")
def index():
    """Speaker — client-side React app, no login or database."""
    log_project_visit("speaker", "Speaker")
    return render_template("speaker/index.html")
