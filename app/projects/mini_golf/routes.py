from flask import Blueprint, render_template

mini_golf_bp = Blueprint(
    "mini_golf",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/mini-golf/static",
)


@mini_golf_bp.route("/")
def index():
    return render_template("mini_golf/index.html")
