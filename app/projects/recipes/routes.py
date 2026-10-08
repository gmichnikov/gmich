from flask import Blueprint, render_template

from app.utils.logging import log_project_visit

recipes_bp = Blueprint(
    "recipes",
    __name__,
    url_prefix="/recipes",
    template_folder="templates",
    static_folder="static",
    static_url_path="/recipes/static",
)

RECIPES = [
    {
        "name": "Pumpkin Banana Muffins",
        "endpoint": "recipes.pumpkin_banana_muffins",
        "blurb": "Ingredients · makes 12",
        "mark": "🎃",
    },
    {
        "name": "Pancakes",
        "endpoint": "recipes.pancakes",
        "blurb": "Ingredients · makes 8–10",
        "mark": "🥞",
    },
    {
        "name": "Falafel",
        "endpoint": "recipes.falafel",
        "blurb": "Ingredients · makes 12–15",
        "mark": "🧆",
    },
]


@recipes_bp.route("/")
def index():
    """Recipe index — public, no login or database."""
    log_project_visit("recipes", "Recipes")
    return render_template("recipes/index.html", recipes=RECIPES)


@recipes_bp.route("/pumpkin-banana-muffins")
def pumpkin_banana_muffins():
    """Pumpkin banana muffins ingredient sheet."""
    log_project_visit("recipes", "Pumpkin Banana Muffins")
    return render_template("recipes/pumpkin_banana_muffins.html")


@recipes_bp.route("/pancakes")
def pancakes():
    """Pancakes ingredient sheet."""
    log_project_visit("recipes", "Pancakes")
    return render_template("recipes/pancakes.html")


@recipes_bp.route("/falafel")
def falafel():
    """Falafel ingredient sheet."""
    log_project_visit("recipes", "Falafel")
    return render_template("recipes/falafel.html")
