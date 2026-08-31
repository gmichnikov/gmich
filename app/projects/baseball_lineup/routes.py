from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.projects.baseball_lineup.models import BluTeam
from app.utils.logging import log_project_visit

baseball_lineup_bp = Blueprint(
    "baseball_lineup",
    __name__,
    url_prefix="/baseball-lineup",
    template_folder="templates",
    static_folder="static",
    static_url_path="/baseball-lineup/static",
)


@baseball_lineup_bp.route("/")
@login_required
def index():
    log_project_visit("baseball_lineup", "Baseball Lineup")
    teams = (
        BluTeam.query.filter_by(user_id=current_user.id)
        .order_by(BluTeam.updated_at.desc())
        .all()
    )
    return render_template("baseball_lineup/index.html", teams=teams)
