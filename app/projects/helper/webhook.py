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

Pipeline B (three-stage LLM):
  9.  Router call -> route: complete_task | add_task | unknown
  10. Specialist call -> extracted fields
  11. Apply side effects (DB writes, confirmation emails)
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
from app.projects.helper.claude import (
    ClaudeResponseError,
    route_email,
    run_complete_task_specialist,
    run_add_task_specialist,
)
from app.projects.helper.reminder_logic import (
    clear_task_reminders,
    parse_reminder_at_iso,
    sync_reminder_with_due_date,
)
from app.projects.helper.email import (
    notify_helper_claude_error_to_admin,
    send_duplicate_task_skipped,
    send_task_confirmation,
    send_task_completed_confirmation,
    send_task_logged_completed_confirmation,
    send_complete_task_failed,
)

logger = logging.getLogger(__name__)

helper_webhook_bp = Blueprint("helper_webhook", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce_already_completed(raw) -> bool:
    """True only when the model explicitly indicates a retrospective completed entry."""
    if raw is True:
        return True
    if raw is False or raw is None:
        return False
    if isinstance(raw, str):
        return raw.strip().lower() in ("true", "1", "yes")
    return False


def _normalize_email(address: str) -> str:
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

    parts = "|".join([
        form.get("sender", ""),
        form.get("recipient", ""),
        form.get("timestamp", ""),
        form.get("subject", ""),
    ])
    return "hash:" + hashlib.sha256(parts.encode()).hexdigest()


def _verify_mailgun_signature(form: dict) -> bool:
    signing_key = os.getenv("MAILGUN_WEBHOOK_SIGNING_KEY", "")
    if not signing_key:
        logger.error("MAILGUN_WEBHOOK_SIGNING_KEY is not set — cannot verify signature")
        return False

    token = form.get("token", "")
    timestamp = form.get("timestamp", "")
    signature = form.get("signature", "")

    if not all([token, timestamp, signature]):
        return False

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


def _handle_claude_error(inbound, group, sender_user, e, stage: str):
    """Log a Claude error, set inbound status, send admin alert."""
    logger.error(
        "Claude error (stage=%s) for inbound_email id=%s: %s",
        stage, inbound.id, e,
        exc_info=True,
    )
    inbound.status = "error"
    db.session.commit()
    detail = {"stage": stage}
    if isinstance(e, ClaudeResponseError) and e.raw_response:
        detail["claude_raw_response"] = e.raw_response[:8000]
    _log_action(inbound, "claude_error", error=str(e), detail=detail)
    try:
        notify_helper_claude_error_to_admin(
            inbound_id=inbound.id,
            group_name=group.name,
            sender_email=sender_user.email,
            error_message=f"[{stage}] {e}",
            raw_response=e.raw_response if isinstance(e, ClaudeResponseError) else None,
        )
    except Exception as notify_err:
        logger.error("Failed to send Helper Claude error admin alert: %s", notify_err, exc_info=True)


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------

def _handle_complete_task(
    inbound, group, sender_user, open_tasks, open_tasks_db,
    subject, body_text, member_names_emails, sender_tz,
):
    """Stage 2a: run complete-task specialist and apply side effects."""
    try:
        specialist_result = run_complete_task_specialist(
            subject=subject,
            body=body_text,
            member_names_emails=member_names_emails,
            sender_tz=sender_tz,
            open_tasks=open_tasks,
        )
    except Exception as e:
        _handle_claude_error(inbound, group, sender_user, e, stage="complete_task_specialist")
        return

    _log_action(inbound, "specialist_complete_task_result", detail={"specialist_response": specialist_result})

    task_id = specialist_result.get("task_id")
    open_task_ids = {t["id"] for t in open_tasks}

    if not task_id or task_id not in open_task_ids:
        logger.warning(
            "Complete-task specialist returned invalid task_id=%s for inbound_email id=%s",
            task_id, inbound.id,
        )
        inbound.status = "processed"
        db.session.commit()
        invalid_task = HelperTask.query.get(task_id) if task_id else None
        _log_action(inbound, "complete_task_invalid_id", detail={
            "task_id": task_id,
            "title": invalid_task.title if invalid_task else None,
            "specialist_response": specialist_result,
        })
        send_complete_task_failed(open_tasks_db, sender_user, group)
        return

    task = HelperTask.query.get(task_id)
    if not task or task.status != "open":
        logger.warning(
            "Complete-task specialist: task id=%s not found or already closed for inbound_email id=%s",
            task_id, inbound.id,
        )
        inbound.status = "processed"
        db.session.commit()
        stale_task = HelperTask.query.get(task_id)
        _log_action(inbound, "complete_task_not_found", detail={
            "task_id": task_id,
            "title": stale_task.title if stale_task else None,
            "specialist_response": specialist_result,
        })
        send_complete_task_failed(open_tasks_db, sender_user, group)
        return

    try:
        task.status = "complete"
        task.completed_by_user_id = sender_user.id
        task.completed_at = datetime.utcnow()
        task.completed_via_inbound_email_id = inbound.id
        clear_task_reminders(task)
        inbound.status = "processed"
        db.session.commit()
        _log_action(inbound, "task_completed", detail={
            "task_id": task.id,
            "title": task.title,
            "specialist_response": specialist_result,
        })
        logger.info("Task id=%s completed via email for inbound_email id=%s", task.id, inbound.id)
        send_task_completed_confirmation(task, sender_user, group)
    except Exception as e:
        db.session.rollback()
        logger.error(
            "Task complete failed for task id=%s inbound_email id=%s: %s",
            task_id, inbound.id, e,
        )
        inbound.status = "error"
        db.session.commit()
        err_task = HelperTask.query.get(task_id) if task_id else None
        _log_action(inbound, "complete_task_error", error=str(e), detail={
            "task_id": task_id,
            "title": err_task.title if err_task else None,
        })


def _handle_add_task(
    inbound, group, sender_user, open_tasks, open_tasks_db,
    subject, body_text, member_names_emails, sender_tz,
):
    """Stage 2b: run add-task specialist and apply side effects."""
    try:
        specialist_result = run_add_task_specialist(
            subject=subject,
            body=body_text,
            member_names_emails=member_names_emails,
            sender_tz=sender_tz,
            open_tasks=open_tasks,
        )
    except Exception as e:
        _handle_claude_error(inbound, group, sender_user, e, stage="add_task_specialist")
        return

    _log_action(inbound, "specialist_add_task_result", detail={"specialist_response": specialist_result})

    already_completed = _coerce_already_completed(specialist_result.get("already_completed"))

    # Duplicate detection
    open_task_ids = {t["id"] for t in open_tasks}
    dup_raw = specialist_result.get("duplicate_of_task_id")
    dup_id = None
    if not already_completed and dup_raw is not None and dup_raw != "":
        try:
            dup_id = int(dup_raw)
        except (TypeError, ValueError):
            dup_id = None

    if not already_completed and dup_id is not None and dup_id in open_task_ids:
        existing = HelperTask.query.get(dup_id)
        if existing and existing.group_id == group.id and existing.status == "open":
            inbound.status = "processed"
            db.session.commit()
            _log_action(inbound, "task_duplicate_skipped", detail={
                "existing_task_id": dup_id,
                "specialist_response": specialist_result,
            })
            notice = send_duplicate_task_skipped(existing, sender_user, group)
            conf_detail = {"to": sender_user.email, "task_id": existing.id, "title": existing.title}
            if notice:
                _log_action(inbound, "duplicate_notice_sent", detail=conf_detail)
            else:
                _log_action(inbound, "duplicate_notice_failed", detail=conf_detail)
            return
        logger.warning(
            "duplicate_of_task_id=%s invalid or not open for inbound_email id=%s; creating new task",
            dup_id, inbound.id,
        )
    elif not already_completed and dup_id is not None:
        logger.warning(
            "duplicate_of_task_id=%s not in open_tasks for inbound_email id=%s; creating new task",
            dup_id, inbound.id,
        )

    title = (specialist_result.get("title") or "").strip()
    due_date_str = specialist_result.get("due_date")
    assignee_email = specialist_result.get("assignee_email")
    notes = (specialist_result.get("notes") or "").strip() or None
    reminder_at_raw = specialist_result.get("reminder_at")

    if not title:
        inbound.status = "error"
        db.session.commit()
        _log_action(inbound, "claude_error", error="add_task specialist missing title", detail={"specialist_response": specialist_result})
        return

    # Parse due_date
    due_date = None
    if due_date_str:
        try:
            from datetime import date
            due_date = date.fromisoformat(due_date_str)
        except (ValueError, TypeError):
            logger.warning("Could not parse due_date '%s' for inbound_email id=%s", due_date_str, inbound.id)

    # Resolve assignee
    assignee_user_id = None
    if assignee_email:
        matched = next(
            (m.user for m in group.members if m.user and m.user.email.lower() == assignee_email.lower()),
            None,
        )
        if matched:
            assignee_user_id = matched.id
        else:
            logger.info("Specialist assignee '%s' not found in group; leaving unset", assignee_email)
    if assignee_user_id is None and not assignee_email:
        assignee_user_id = sender_user.id

    # Parse explicit reminder_at from specialist (§13)
    explicit_reminder_at = None
    if reminder_at_raw and not already_completed:
        explicit_reminder_at = parse_reminder_at_iso(reminder_at_raw)
        if explicit_reminder_at is None:
            logger.warning(
                "Could not parse reminder_at '%s' from specialist for inbound_email id=%s; ignoring",
                reminder_at_raw, inbound.id,
            )
        elif explicit_reminder_at <= datetime.utcnow():
            logger.warning(
                "Specialist reminder_at '%s' is not in the future for inbound_email id=%s; ignoring",
                reminder_at_raw, inbound.id,
            )
            explicit_reminder_at = None

    try:
        if already_completed:
            task = HelperTask(
                group_id=group.id,
                title=title,
                due_date=due_date,
                notes=notes,
                assignee_user_id=assignee_user_id,
                created_by_user_id=sender_user.id,
                status="complete",
                completed_by_user_id=sender_user.id,
                completed_at=datetime.utcnow(),
                completed_via_inbound_email_id=inbound.id,
                source_inbound_email_id=inbound.id,
            )
        else:
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

        if not already_completed:
            # §13 precedence: explicit reminder_at wins over sync_reminder_with_due_date
            if explicit_reminder_at is not None:
                task.reminder_at = explicit_reminder_at
                task.reminder_sent_at = None
                logger.info(
                    "Explicit reminder_at=%s set for task id=%s from inbound_email id=%s",
                    explicit_reminder_at, task.id, inbound.id,
                )
            else:
                sync_reminder_with_due_date(task)

        inbound.status = "processed"
        db.session.commit()

        reminder_detail = {"reminder_at_raw": reminder_at_raw, "reminder_at_applied": str(explicit_reminder_at) if explicit_reminder_at else None}

        if already_completed:
            _log_action(inbound, "task_logged_completed", detail={
                "task_id": task.id,
                "title": title,
                "due_date": due_date_str,
                "assignee_user_id": assignee_user_id,
                "specialist_response": specialist_result,
            })
            logger.info("Task id=%s logged as completed for inbound_email id=%s", task.id, inbound.id)
            confirmed = send_task_logged_completed_confirmation(task, sender_user, group)
        else:
            _log_action(inbound, "task_created", detail={
                "task_id": task.id,
                "title": title,
                "due_date": due_date_str,
                "assignee_user_id": assignee_user_id,
                "reminder": reminder_detail,
                "specialist_response": specialist_result,
            })
            logger.info("Task id=%s created for inbound_email id=%s", task.id, inbound.id)
            confirmed = send_task_confirmation(task, sender_user, group)

        conf_detail = {"to": sender_user.email, "task_id": task.id, "title": task.title}
        if confirmed:
            _log_action(inbound, "confirmation_sent", detail=conf_detail)
        else:
            _log_action(inbound, "confirmation_failed", detail=conf_detail)

    except Exception as e:
        db.session.rollback()
        logger.error("Task insert failed for inbound_email id=%s: %s", inbound.id, e)
        inbound.status = "error"
        db.session.commit()
        _log_action(inbound, "task_insert_error", error=str(e), detail={"title": title})


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
    # Step 3 — Duplicate check
    # ------------------------------------------------------------------
    existing = HelperInboundEmail.query.filter_by(idempotency_key=idempotency_key).first()
    if existing:
        logger.info("Duplicate inbound email, idempotency_key=%s", idempotency_key)
        if existing.status != "duplicate":
            existing.status = "duplicate"
            db.session.commit()
            _log_action(existing, "duplicate_skipped", detail={"idempotency_key": idempotency_key})
        return ("", 200)

    # ------------------------------------------------------------------
    # Step 4 — Insert inbound row
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
        logger.warning("Invalid Mailgun signature for inbound_email id=%s", inbound.id)
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
        logger.info("Unknown recipient: %s", recipient_normalized)
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
        logger.info("Unknown sender user: %s", sender_normalized)
        inbound.status = "sender_not_allowed"
        db.session.commit()
        _log_action(inbound, "sender_unknown_user", detail={"sender": sender_raw})
        return ("", 200)

    membership = HelperGroupMember.query.filter_by(
        group_id=group.id,
        user_id=sender_user.id,
    ).first()

    if not membership:
        logger.info("Sender %s is not a member of group %s", sender_normalized, group.id)
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
        logger.info("Empty content for inbound_email id=%s", inbound.id)
        inbound.status = "empty_content"
        db.session.commit()
        _log_action(inbound, "empty_content")
        return ("", 200)

    # ------------------------------------------------------------------
    # Pipeline B — Three-stage LLM pipeline
    # ------------------------------------------------------------------
    inbound.status = "pending_llm"
    db.session.commit()
    logger.info(
        "Inbound email id=%s accepted for group=%s, sender_user=%s — starting router",
        inbound.id, group.id, sender_user.id,
    )

    member_names_emails = [
        (m.user.full_name, m.user.email)
        for m in group.members
        if m.user is not None
    ]
    sender_tz = sender_user.time_zone or "UTC"

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

    # ------------------------------------------------------------------
    # Step 9 — Router call
    # ------------------------------------------------------------------
    try:
        router_result = route_email(
            subject=subject,
            body=body_text,
            member_names_emails=member_names_emails,
            sender_tz=sender_tz,
            open_tasks=open_tasks,
        )
    except Exception as e:
        _handle_claude_error(inbound, group, sender_user, e, stage="router")
        return ("", 200)

    route = router_result.get("route", "unknown")
    _log_action(inbound, "router_result", detail={"route": route, "router_response": router_result})
    logger.info("Router classified inbound_email id=%s as route=%s", inbound.id, route)

    # ------------------------------------------------------------------
    # Step 10/11 — Dispatch to specialist + apply side effects
    # ------------------------------------------------------------------
    if route == "unknown":
        inbound.status = "processed"
        db.session.commit()
        logger.info("Router returned unknown for inbound_email id=%s", inbound.id)
        return ("", 200)

    if route == "complete_task":
        _handle_complete_task(
            inbound, group, sender_user, open_tasks, open_tasks_db,
            subject, body_text, member_names_emails, sender_tz,
        )
        return ("", 200)

    if route == "add_task":
        _handle_add_task(
            inbound, group, sender_user, open_tasks, open_tasks_db,
            subject, body_text, member_names_emails, sender_tz,
        )
        return ("", 200)

    # Unexpected route value — treat as unknown
    logger.warning("Unexpected route value '%s' for inbound_email id=%s", route, inbound.id)
    inbound.status = "processed"
    db.session.commit()
    _log_action(inbound, "unknown_intent", detail={"router_response": router_result})
    return ("", 200)
