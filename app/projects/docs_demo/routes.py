from flask import Blueprint, render_template

docs_demo_bp = Blueprint(
    "docs_demo",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/docs-demo/static",
)


@docs_demo_bp.route("/")
def index():
    """Display the Docs Demo page."""
    return render_template("docs_demo/index.html")
