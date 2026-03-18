from flask import Blueprint, jsonify, render_template, request

from app import csrf
from app.projects.docs_demo.gemini_service import generate_comments, generate_text

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


@docs_demo_bp.route("/api/generate", methods=["POST"])
@csrf.exempt
def api_generate():
    """
    Proxy LLM calls to Gemini.
    Body: { "type": "text" | "comments", "prompt": "...", "text": "..." }
    """
    try:
        data = request.get_json() or {}
        req_type = data.get("type")
        prompt = data.get("prompt")
        text = data.get("text", "")

        if not req_type or req_type not in ("text", "comments"):
            return jsonify({"error": "Invalid or missing 'type'"}), 400
        if prompt is None:
            return jsonify({"error": "Missing 'prompt'"}), 400
        if text is None:
            text = ""

        if req_type == "text":
            result = generate_text(prompt, text)
            return jsonify({"result": result})

        if req_type == "comments":
            comments = generate_comments(prompt, text)
            return jsonify({"comments": comments})

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Something went wrong. Please try again."}), 500
