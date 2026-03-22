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
    """Dice Roll — play view (client-side only)."""
    return render_template("dice_roll/index.html")


@dice_roll_bp.route("/setup")
def setup():
    """Choose how many dice (1, 2, or 5); kept in localStorage on the client."""
    return render_template("dice_roll/setup.html")
