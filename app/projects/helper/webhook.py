"""
Mailgun inbound webhook handler for the Helper project.

Pipeline A:
  1. Parse POST fields
  2. Compute idempotency key
  3. Check for duplicate
  4. Insert helper_inbound_email row
  5. Verify Mailgun signature
  6. Resolve recipient -> group
  7. Resolve sender -> User + membership check
  8. Check for empty content

Pipeline B:
  9. Call Claude -> parse intent
  10. Create helper_task on add_task intent
"""
import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime

from flask import Blueprint, request

from app import csrf, db
from app.models import User
from app.projects.helper.models import (
    HelperActionLog,
    HelperGroup,
    HelperGroupMember,
    HelperInboundEmail,
    HelperTask,
)
from app.projects.helper.claude import parse_email_for_task
from app.projects.helper.email import (
    send_task_confirmation,
    send_task_completed_confirmation,
    send_complete_task_failed,
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
    # Pipeline B — Claude + task creation
    # ------------------------------------------------------------------
    inbound.status = "pending_llm"
    db.session.commit()
    logger.info(
        f"Inbound email id={inbound.id} accepted for group={group.id}, "
        f"sender_user={sender_user.id}, calling Claude"
    )

    # Build member list for Claude prompt
    member_names_emails = [
        (m.user.full_name, m.user.email)
        for m in group.members
        if m.user is not None
    ]

    # Fetch open tasks for this group to pass as context
    open_tasks_db = (
        HelperTask.query
        .filter_by(group_id=group.id, status="open")
        .order_by(HelperTask.created_at.asc())
        .all()
    )
    open_tasks = [
        {"id": t.id, "title": t.title, "notes": t.notes}
        for t in open_tasks_db
    ]

    # Step 9 — Call Claude
    try:
        result = parse_email_for_task(
            subject=subject,
            body=body_text,
            member_names_emails=member_names_emails,
            sender_tz=sender_user.time_zone or "UTC",
            open_tasks=open_tasks,
        )
    except Exception as e:
        logger.error(f"Claude error for inbound_email id={inbound.id}: {e}")
        inbound.status = "error"
        db.session.commit()
        _log_action(inbound, "claude_error", error=str(e))
        return ("", 200)

    intent = result.get("intent", "unknown")

    # Step 10 — Handle intent
    if intent == "unknown":
        inbound.status = "processed"
        db.session.commit()
        _log_action(inbound, "unknown_intent", detail={"claude_response": result})
        logger.info(f"Claude returned unknown intent for inbound_email id={inbound.id}")
        return ("", 200)

    if intent == "add_task":
        title = (result.get("title") or "").strip()
        due_date_str = result.get("due_date")
        assignee_email = result.get("assignee_email")

        if not title:
            inbound.status = "error"
            db.session.commit()
            _log_action(inbound, "claude_error", error="add_task intent missing title", detail={"claude_response": result})
            return ("", 200)

        notes = (result.get("notes") or "").strip() or None

        # Parse due_date
        due_date = None
        if due_date_str:
            try:
                from datetime import date
                due_date = date.fromisoformat(due_date_str)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse due_date '{due_date_str}' for inbound_email id={inbound.id}")

        # Resolve assignee — match by email against group members; default to sender
        assignee_user_id = None
        if assignee_email:
            matched = next(
                (m.user for m in group.members if m.user and m.user.email.lower() == assignee_email.lower()),
                None,
            )
            if matched:
                assignee_user_id = matched.id
            else:
                logger.info(f"Claude assignee '{assignee_email}' not found in group; leaving unset")
        # If no assignee specified by Claude, default to sender
        if assignee_user_id is None and not assignee_email:
            assignee_user_id = sender_user.id

        # Insert task
        try:
                task = HelperTask(
                    group_id=group.id,
                    title=title,
                    due_date=due_date,
                    notes=notes,
                    assignee_user_id=assignee_user_id,
                    created_by_user_id=sender_user.id,
                    status="open",
                    source_inbound_email_id=inbound.id,
                )
            db.session.add(task)
            db.session.flush()
            inbound.status = "processed"
            db.session.commit()
            _log_action(inbound, "task_created", detail={
                "task_id": task.id,
                "title": title,
                "due_date": due_date_str,
                "assignee_user_id": assignee_user_id,
                "claude_response": result,
            })
            logger.info(f"Task id={task.id} created for inbound_email id={inbound.id}")
            confirmed = send_task_confirmation(task, sender_user, group)
            if confirmed:
                _log_action(inbound, "confirmation_sent", detail={"to": sender_user.email})
            else:
                _log_action(inbound, "confirmation_failed", detail={"to": sender_user.email})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Task insert failed for inbound_email id={inbound.id}: {e}")
            inbound.status = "error"
            db.session.commit()
            _log_action(inbound, "task_insert_error", error=str(e))

        return ("", 200)

    if intent == "complete_task":
        task_id = result.get("task_id")

        # Validate task_id is in the open tasks we sent Claude
        open_task_ids = {t["id"] for t in open_tasks}
        if not task_id or task_id not in open_task_ids:
            logger.warning(
                f"Claude returned complete_task with invalid task_id={task_id} "
                f"for inbound_email id={inbound.id}"
            )
            inbound.status = "processed"
            db.session.commit()
            _log_action(inbound, "complete_task_invalid_id", detail={
                "task_id": task_id,
                "claude_response": result,
            })
            send_complete_task_failed(open_tasks_db, sender_user, group)
            return ("", 200)

        task = HelperTask.query.get(task_id)
        if not task or task.status != "open":
            logger.warning(
                f"Claude returned complete_task but task id={task_id} "
                f"not found or already closed for inbound_email id={inbound.id}"
            )
            inbound.status = "processed"
            db.session.commit()
            _log_action(inbound, "complete_task_not_found", detail={
                "task_id": task_id,
                "claude_response": result,
            })
            send_complete_task_failed(open_tasks_db, sender_user, group)
            return ("", 200)

        try:
            task.status = "complete"
            task.completed_by_user_id = sender_user.id
            task.completed_at = datetime.utcnow()
            inbound.status = "processed"
            db.session.commit()
            _log_action(inbound, "task_completed", detail={
                "task_id": task.id,
                "title": task.title,
                "claude_response": result,
            })
            logger.info(
                f"Task id={task.id} completed via email for inbound_email id={inbound.id}"
            )
            send_task_completed_confirmation(task, sender_user, group)
        except Exception as e:
            db.session.rollback()
            logger.error(
                f"Task complete failed for task id={task_id} "
                f"inbound_email id={inbound.id}: {e}"
            )
            inbound.status = "error"
            db.session.commit()
            _log_action(inbound, "complete_task_error", error=str(e))

        return ("", 200)

    # Unknown intent value from Claude
    inbound.status = "processed"
    db.session.commit()
    _log_action(inbound, "unknown_intent", detail={"claude_response": result})
    return ("", 200)
