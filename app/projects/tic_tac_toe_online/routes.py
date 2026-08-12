from flask import Blueprint, render_template

from app.utils.logging import log_project_visit

tic_tac_toe_online_bp = Blueprint(
    "tic_tac_toe_online",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/tic-tac-toe-online/static",
)


@tic_tac_toe_online_bp.route("/")
def index():
    """Landing page: create a new room or join an existing one via link."""
    log_project_visit("tic_tac_toe_online", "Tic-Tac-Toe Online")
    return render_template("tic_tac_toe_online/index.html")
