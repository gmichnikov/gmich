"""
Sports Schedules - Public UI for viewing sports schedules.
No login required. No database usage.
"""

from flask import Blueprint, render_template

sports_schedules_bp = Blueprint(
    "sports_schedules",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/projects/sports_schedules/static",
    url_prefix="/sports-schedules",
)


@sports_schedules_bp.route("/")
def index():
    """Placeholder - will be the main schedule viewer."""
    return render_template("sports_schedules/index.html")
