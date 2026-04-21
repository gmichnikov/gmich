"""Process due Helper task reminders (called from Heroku Scheduler / CLI)."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import joinedload

from app import db
from app.projects.helper.email import send_task_reminder_email
from app.projects.helper.models import HelperReminderLog, HelperTask
from app.projects.helper.reminder_logic import reminder_recipient_user

logger = logging.getLogger(__name__)


def _log_reminder(task: HelperTask, action_type: str, detail=None, error: str | None = None):
    row = HelperReminderLog(
        task_id=task.id,
        action_type=action_type,
        detail=detail,
        error_message=error,
    )
    db.session.add(row)


def run_pending_reminders(limit: int = 100) -> dict:
    """
    Find open tasks with reminder_at due and reminder_sent_at empty; send email;
    set reminder_sent_at on success. Returns counts for logging.
    """
    now = datetime.utcnow()
    tasks = (
        HelperTask.query.options(
            joinedload(HelperTask.assignee),
            joinedload(HelperTask.creator),
            joinedload(HelperTask.group),
        )
        .filter(
            HelperTask.status == "open",
            HelperTask.reminder_at.isnot(None),
            HelperTask.reminder_at <= now,
            HelperTask.reminder_sent_at.is_(None),
        )
        .order_by(HelperTask.reminder_at.asc())
        .limit(limit)
        .all()
    )

    sent = 0
    failed = 0
    for task in tasks:
        recipient = reminder_recipient_user(task)
        if not recipient or not getattr(recipient, "email", None):
            logger.warning("Reminder skipped: no recipient for task_id=%s", task.id)
            try:
                _log_reminder(
                    task,
                    "reminder_failed",
                    detail={"reason": "no_recipient"},
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
            failed += 1
            continue

        try:
            ok = send_task_reminder_email(task, recipient, task.group)
            if ok:
                task.reminder_sent_at = now
                _log_reminder(
                    task,
                    "reminder_sent",
                    detail={"to": recipient.email},
                )
                db.session.commit()
                sent += 1
            else:
                _log_reminder(
                    task,
                    "reminder_failed",
                    detail={"to": recipient.email, "reason": "send_failed"},
                )
                db.session.commit()
                failed += 1
        except Exception as e:
            db.session.rollback()
            logger.exception("Reminder send error task_id=%s", task.id)
            try:
                task_ref = HelperTask.query.get(task.id)
                if task_ref:
                    _log_reminder(task_ref, "reminder_failed", error=str(e))
                    db.session.commit()
            except Exception:
                db.session.rollback()
            failed += 1

    result = {
        "sent": sent,
        "failed": failed,
        "candidates": len(tasks),
    }
    logger.info("Helper reminders run: %s", result)
    return result
