from flask import Blueprint, render_template

dice_roll_bp = Blueprint(
    "dice_roll",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/dice-roll/static",
)


@dice_roll_bp.route("/")
def index():
    """Dice Roll — game night helper (client-side only; no project APIs)."""
    return render_template("dice_roll/index.html")
