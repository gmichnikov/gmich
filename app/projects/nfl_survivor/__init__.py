from flask import Blueprint

nfl_survivor_bp = Blueprint(
    "nfl_survivor",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/projects/nfl_survivor/static",
)

from app.projects.nfl_survivor import routes  # noqa: E402, F401
