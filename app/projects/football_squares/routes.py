from flask import render_template
from flask_login import login_required
from app.projects.football_squares import football_squares_bp

@football_squares_bp.route("/")
@login_required
def index():
    return render_template("football_squares/index.html")
