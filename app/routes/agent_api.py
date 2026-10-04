"""
Generic API endpoint for autonomous AI agents to send notifications.
Protected by a simple Bearer token (AGENT_EMAIL_NOTIFY_SECRET).
"""
import os
import logging
from flask import Blueprint, request, jsonify
from app import csrf
from app.utils.email_service import send_email

logger = logging.getLogger(__name__)

agent_api_bp = Blueprint("agent_api", __name__, url_prefix="/api/agent")


def _verify_agent_key():
    """Verify Bearer token against AGENT_EMAIL_NOTIFY_SECRET environment variable."""
    expected_key = os.getenv("AGENT_EMAIL_NOTIFY_SECRET", "").strip()
    if not expected_key:
        logger.error("AGENT_EMAIL_NOTIFY_SECRET is not configured in environment.")
        return False, "Server agent notification secret not configured"

    auth_header = request.headers.get("Authorization", "").strip()
    if not auth_header.startswith("Bearer "):
        return False, "Missing or invalid Authorization header (expected 'Bearer <key>')"

    token = auth_header[len("Bearer "):].strip()
    if token != expected_key:
        return False, "Invalid agent key"

    return True, None


@agent_api_bp.route("/notify", methods=["POST"])
@csrf.exempt
def notify():
    """
    Send an email notification from an autonomous agent to ADMIN_EMAIL.
    
    JSON Body:
      - subject: Email subject line (required)
      - body: Plain text or markdown message content (required)
      - html: Optional HTML version
    """
    is_valid, error_msg = _verify_agent_key()
    if not is_valid:
        return jsonify({"error": error_msg}), 401

    data = request.get_json(silent=True) or {}
    subject = data.get("subject", "").strip()
    body_text = data.get("body", "").strip()
    body_html = data.get("html")

    if not subject:
        return jsonify({"error": "'subject' is required"}), 400
    if not body_text and not body_html:
        return jsonify({"error": "'body' or 'html' is required"}), 400

    admin_email = os.getenv("ADMIN_EMAIL")
    if not admin_email:
        return jsonify({"error": "ADMIN_EMAIL is not configured"}), 500

    try:
        send_email(
            to_email=admin_email,
            subject=subject,
            text_content=body_text or "Please see HTML message",
            html_content=body_html,
            from_name="Agent Assistant",
        )
        logger.info(f"Successfully dispatched agent notification to {admin_email}")
        return jsonify({"success": True, "message": "Notification sent"}), 200
    except Exception as e:
        logger.error(f"Failed to dispatch agent notification: {e}")
        return jsonify({"error": str(e)}), 500
