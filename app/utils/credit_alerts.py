"""Admin notification when a user's credit balance reaches zero.

Credits are deducted from eight different places, each writing to User.credits
directly. Rather than editing every call site (and needing to remember for the
ninth), this watches the SQLAlchemy session for the balance crossing from
positive to zero and notifies the admin after the transaction commits.
"""

import logging
import os
from datetime import datetime

from sqlalchemy import event, inspect

from app.utils.email_service import send_email

logger = logging.getLogger(__name__)

# Where pending notifications wait between the flush that detects them and the
# commit that makes them real.
SESSION_KEY = "credit_alerts_exhausted"

# This send can happen mid-request, so it must not stall a web worker.
MAILGUN_TIMEOUT_SECONDS = 10

_listeners_registered = False


def _describe_source():
    """Best-effort description of what spent the last credit."""
    try:
        from flask import has_request_context, request

        if not has_request_context():
            return "a scheduled job"
        if request.blueprint:
            return request.blueprint.replace("_", " ").title()
        return request.path or "the website"
    except Exception:
        return "an unknown source"


def build_credits_exhausted_email(user_email, user_name, source, occurred_at):
    """Return (subject, text_content, html_content) for the admin alert."""
    base_url = os.getenv("BASE_URL", "https://gregmichnikov.com").rstrip("/")
    add_credits_url = f"{base_url}/admin/add_credits"
    users_url = f"{base_url}/admin/users"
    when = occurred_at.strftime("%Y-%m-%d %H:%M UTC")

    subject = f"Out of credits: {user_email}"

    text_content = f"""{user_name} ({user_email}) just used their last credit.

Spent via: {source}
When: {when}

Until they get more credits, anything that costs a credit will stop working for
them. Scheduled daily emails and reminders will be skipped silently.

Add credits:  {add_credits_url}
All users:    {users_url}

gregmichnikov.com
"""

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .alert-box {{ background-color: #f8d7da; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #dc3545; }}
        .info-box {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        .btn {{ display: inline-block; padding: 12px 24px; background-color: #007bff; color: #ffffff !important; text-decoration: none; border-radius: 5px; margin: 20px 0; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Out of Credits</h2>
        <div class="alert-box">
            <p style="margin: 0;"><strong>{user_name}</strong> ({user_email}) just used their last credit.</p>
        </div>

        <div class="info-box">
            <p style="margin: 0 0 5px 0;"><strong>Spent via:</strong> {source}</p>
            <p style="margin: 0;"><strong>When:</strong> {when}</p>
        </div>

        <p>Until they get more credits, anything that costs a credit will stop working
        for them. Scheduled daily emails and reminders will be skipped silently.</p>

        <a href="{add_credits_url}" class="btn">Add Credits</a>
        <p><a href="{users_url}">View all users and credit usage</a></p>

        <div class="footer">
            <p>gregmichnikov.com</p>
        </div>
    </div>
</body>
</html>
"""

    return subject, text_content, html_content


def notify_admin_credits_exhausted(user_email, user_name, source, occurred_at=None):
    """Email ADMIN_EMAIL that a user ran out of credits.

    Skips quietly if ADMIN_EMAIL is unset. Logs failures; never raises, so a
    Mailgun outage can't roll back the work that spent the credit.
    """
    admin_email = os.getenv("ADMIN_EMAIL", "").strip()
    if not admin_email:
        logger.warning("ADMIN_EMAIL not set; skipping credits-exhausted alert")
        return None

    subject, text_content, html_content = build_credits_exhausted_email(
        user_email, user_name, source, occurred_at or datetime.utcnow()
    )

    try:
        response = send_email(
            to_email=admin_email,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            timeout=MAILGUN_TIMEOUT_SECONDS,
        )
        logger.info("Sent credits-exhausted alert for %s", user_email)
        return response
    except Exception:
        logger.exception("Failed to send credits-exhausted alert for %s", user_email)
        return None


def _collect_exhausted_users(session):
    """Find users whose credits just went from positive to zero or below."""
    from app.models import User

    exhausted = []
    for obj in session.dirty:
        if not isinstance(obj, User):
            continue

        history = inspect(obj).attrs.credits.history
        if not history.has_changes():
            continue

        # Empty when the previous value was never loaded, which means we can't
        # tell whether this is a crossing. Skipping is better than false alarms.
        if not history.deleted or not history.added:
            continue

        old_value = history.deleted[0] or 0
        new_value = history.added[0] or 0
        if old_value > 0 and new_value <= 0:
            exhausted.append(
                {
                    "user_id": obj.id,
                    "email": obj.email,
                    "name": obj.short_name or obj.full_name or obj.email,
                    "source": _describe_source(),
                    "occurred_at": datetime.utcnow(),
                }
            )

    return exhausted


def init_credit_alerts(db):
    """Attach the session listeners. Safe to call more than once."""
    global _listeners_registered
    if _listeners_registered:
        return
    _listeners_registered = True

    from app.models import User as UserModel

    @event.listens_for(UserModel.credits, "set", active_history=True)
    def _keep_previous_credits(target, value, oldvalue, initiator):
        """Registered for its active_history flag rather than its body.

        Without it, assigning to credits on an expired instance throws away the
        old value, and _collect_exhausted_users can't tell a balance crossing
        zero from any other write.
        """

    @event.listens_for(db.session, "before_flush")
    def _detect_exhaustion(session, flush_context, instances):
        from app.models import LogEntry

        exhausted = _collect_exhausted_users(session)
        if not exhausted:
            return

        pending = session.info.setdefault(SESSION_KEY, [])
        already_queued = {entry["email"] for entry in pending}

        for entry in exhausted:
            if entry["email"] in already_queued:
                continue
            pending.append(entry)
            # Written inside the same transaction, so the log records that the
            # user hit zero even if the email later fails to send.
            session.add(
                LogEntry(
                    project="admin",
                    category="Credits Exhausted",
                    actor_id=entry["user_id"],
                    description=(
                        f"{entry['email']} used their last credit via {entry['source']}"
                    ),
                )
            )

    @event.listens_for(db.session, "after_commit")
    def _send_alerts(session):
        pending = session.info.pop(SESSION_KEY, None)
        if not pending:
            return
        for entry in pending:
            notify_admin_credits_exhausted(
                entry["email"], entry["name"], entry["source"], entry["occurred_at"]
            )

    @event.listens_for(db.session, "after_soft_rollback")
    def _discard_alerts(session, previous_transaction):
        session.info.pop(SESSION_KEY, None)
