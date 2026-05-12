from flask import Blueprint, render_template

from app.utils.logging import log_project_visit

camps_bp = Blueprint(
    "camps",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/camps/static",
    url_prefix="/camps",
)


@camps_bp.route("/")
def index():
    log_project_visit("camps", "Camps")
    return render_template("camps/index.html")
