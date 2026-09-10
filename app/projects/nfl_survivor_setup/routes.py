from flask import Blueprint, render_template

from app.utils.logging import log_project_visit

nfl_survivor_setup_bp = Blueprint(
    "nfl_survivor_setup",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/nfl-survivor-setup/static",
)


@nfl_survivor_setup_bp.route("/")
def index():
    """Public setup and rules page — no login required."""
    log_project_visit("nfl_survivor_setup", "NFL Survivor Setup and Rules")
    return render_template("nfl_survivor_setup/index.html")
