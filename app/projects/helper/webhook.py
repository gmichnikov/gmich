"""
Mailgun inbound webhook handler for the Helper project.

Pipeline A (this file):
  1. Parse POST fields
  2. Compute idempotency key
  3. Check for duplicate
  4. Insert helper_inbound_email row
  5. Verify Mailgun signature
  6. Resolve recipient -> group
  7. Resolve sender -> User + membership check
  8. Check for empty content

Pipeline B (Phase 5):
  Claude + task creation (not implemented here)
"""
import hashlib
import hmac
import json
import logging
import os
import time

from flask import Blueprint, request

from app import csrf, db
from app.models import User
from app.projects.helper.models import (
    HelperActionLog,
    HelperGroup,
    HelperGroupMember,
    HelperInboundEmail,
)

logger = logging.getLogger(__name__)

helper_webhook_bp = Blueprint("helper_webhook", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_email(address: str) -> str:
    """Lowercase and strip whitespace from an email address."""
    return address.strip().lower()


def _compute_idempotency_key(form: dict) -> str:
    """
    Extract Message-Id from message-headers if available; otherwise fall back
    to a SHA-256 hash of sender|recipient|timestamp|subject.
    """
    raw_headers = form.get("message-headers", "")
    try:
        headers = json.loads(raw_headers)
        for name, value in headers:
            if name.lower() == "message-id":
                normalized = value.strip().strip("<>").lower()
                if normalized:
                    return normalized
    except Exception:
        pass

    # Fallback
    parts = "|".join([
        form.get("sender", ""),
        form.get("recipient", ""),
        form.get("timestamp", ""),
        form.get("subject", ""),
    ])
    return "hash:" + hashlib.sha256(parts.encode()).hexdigest()


def _verify_mailgun_signature(form: dict) -> bool:
    """
    Verify Mailgun webhook signature per Mailgun docs.
    Requires MAILGUN_WEBHOOK_SIGNING_KEY env var.
    """
    signing_key = os.getenv("MAILGUN_WEBHOOK_SIGNING_KEY", "")
    if not signing_key:
        logger.error("MAILGUN_WEBHOOK_SIGNING_KEY is not set — cannot verify signature")
        return False

    token = form.get("token", "")
    timestamp = form.get("timestamp", "")
    signature = form.get("signature", "")

    if not all([token, timestamp, signature]):
        return False

    # Reject stale timestamps (> 5 minutes skew)
    try:
        if abs(time.time() - int(timestamp)) > 300:
            logger.warning("Mailgun webhook timestamp is too old or too far in the future")
            return False
    except (ValueError, TypeError):
        return False

    expected = hmac.new(
        signing_key.encode("utf-8"),
        msg=(timestamp + token).encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def _log_action(inbound_email: HelperInboundEmail, action_type: str, detail: dict = None, error: str = None):
    """Insert a helper_action_log row linked to the given inbound email."""
    log = HelperActionLog(
        inbound_email_id=inbound_email.id,
        action_type=action_type,
        detail=detail,
        error_message=error,
    )
    db.session.add(log)
    db.session.commit()


# ---------------------------------------------------------------------------
# Webhook route
# ---------------------------------------------------------------------------

@helper_webhook_bp.route("/hooks/helper/mailgun", methods=["POST"])
@csrf.exempt
def mailgun_inbound():
    form = request.form

    # ------------------------------------------------------------------
    # Step 1 — Parse fields
    # ------------------------------------------------------------------
    recipient_raw = form.get("recipient", "")
    sender_raw = form.get("sender", "")
    subject = form.get("subject", "").strip()
    body_text = (form.get("stripped-text") or form.get("body-plain") or "").strip()
    mailgun_timestamp = form.get("timestamp", "")

    recipient_normalized = _normalize_email(recipient_raw)
    sender_normalized = _normalize_email(sender_raw)

    # ------------------------------------------------------------------
    # Step 2 — Compute idempotency key
    # ------------------------------------------------------------------
    idempotency_key = _compute_idempotency_key(form)

    # ------------------------------------------------------------------
    # Step 3 — Duplicate check (before inserting a new row)
    # ------------------------------------------------------------------
    existing = HelperInboundEmail.query.filter_by(idempotency_key=idempotency_key).first()
    if existing:
        logger.info(f"Duplicate inbound email, idempotency_key={idempotency_key}")
        if existing.status != "duplicate":
            existing.status = "duplicate"
            db.session.commit()
            _log_action(existing, "duplicate_skipped", detail={"idempotency_key": idempotency_key})
        return ("", 200)

    # ------------------------------------------------------------------
    # Step 4 — Insert inbound row early (captures every POST for audit)
    # ------------------------------------------------------------------
    inbound = HelperInboundEmail(
        idempotency_key=idempotency_key,
        recipient=recipient_normalized,
        sender_raw=sender_raw,
        subject=subject or None,
        body_text=body_text or None,
        status="received",
        mailgun_timestamp=mailgun_timestamp or None,
    )
    db.session.add(inbound)
    db.session.commit()

    # ------------------------------------------------------------------
    # Step 5 — Verify Mailgun signature
    # ------------------------------------------------------------------
    if not _verify_mailgun_signature(form):
        logger.warning(f"Invalid Mailgun signature for inbound_email id={inbound.id}")
        inbound.status = "signature_invalid"
        inbound.signature_valid = False
        db.session.commit()
        _log_action(inbound, "signature_invalid")
        return ("", 200)

    inbound.signature_valid = True
    db.session.commit()

    # ------------------------------------------------------------------
    # Step 6 — Resolve recipient -> group
    # ------------------------------------------------------------------
    group = HelperGroup.query.filter(
        db.func.lower(HelperGroup.inbound_email) == recipient_normalized
    ).first()

    if not group:
        logger.info(f"Unknown recipient: {recipient_normalized}")
        inbound.status = "unknown_recipient"
        db.session.commit()
        _log_action(inbound, "unknown_recipient", detail={"recipient": recipient_normalized})
        return ("", 200)

    inbound.group_id = group.id
    db.session.commit()

    # ------------------------------------------------------------------
    # Step 7 — Resolve sender -> User + membership check
    # ------------------------------------------------------------------
    sender_user = User.query.filter(
        db.func.lower(User.email) == sender_normalized
    ).first()

    if not sender_user:
        logger.info(f"Unknown sender user: {sender_normalized}")
        inbound.status = "sender_not_allowed"
        db.session.commit()
        _log_action(inbound, "sender_unknown_user", detail={"sender": sender_raw})
        return ("", 200)

    membership = HelperGroupMember.query.filter_by(
        group_id=group.id,
        user_id=sender_user.id,
    ).first()

    if not membership:
        logger.info(f"Sender {sender_normalized} is not a member of group {group.id}")
        inbound.status = "sender_not_allowed"
        inbound.sender_user_id = sender_user.id
        db.session.commit()
        _log_action(inbound, "sender_not_member", detail={"sender": sender_raw, "group_id": group.id})
        return ("", 200)

    inbound.sender_user_id = sender_user.id
    db.session.commit()

    # ------------------------------------------------------------------
    # Step 8 — Empty content check
    # ------------------------------------------------------------------
    if not subject and not body_text:
        logger.info(f"Empty content for inbound_email id={inbound.id}")
        inbound.status = "empty_content"
        db.session.commit()
        _log_action(inbound, "empty_content")
        return ("", 200)

    # ------------------------------------------------------------------
    # Pipeline A complete — ready for Claude (Phase 5)
    # ------------------------------------------------------------------
    inbound.status = "pending_llm"
    db.session.commit()
    logger.info(
        f"Inbound email id={inbound.id} accepted for group={group.id}, "
        f"sender_user={sender_user.id}, status=pending_llm"
    )

    return ("", 200)
