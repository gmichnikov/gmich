from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

kids_words_bp = Blueprint("kids_words", __name__, template_folder="templates")


@kids_words_bp.route("/")
def index():
    """Kids Words - placeholder route"""
    log_project_visit("kids_words", "Kids Words")
    return render_template("kids_words/index.html")
