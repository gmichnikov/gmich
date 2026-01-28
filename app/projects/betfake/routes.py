from flask import Blueprint

betfake_bp = Blueprint("betfake", __name__, template_folder="templates")

@betfake_bp.route('/')
def index():
    return "BetFake - Coming Soon"
