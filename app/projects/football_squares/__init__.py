from flask import Blueprint

football_squares_bp = Blueprint(
    "football_squares",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/projects/football_squares/static",
)

from app.projects.football_squares import routes
