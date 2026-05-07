from flask import Blueprint, render_template
from flask_login import login_required

from app.utils.logging import log_project_visit

kids_ai_bp = Blueprint(
    "kids_ai",
    __name__,
    url_prefix="/kids-ai",
    template_folder="templates",
    static_folder="static",
    static_url_path="/kids-ai/static",
)


@kids_ai_bp.route("/")
@login_required
def index():
    log_project_visit("kids_ai", "Kids AI")
    return render_template("kids_ai/index.html")
