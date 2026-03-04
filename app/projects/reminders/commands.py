"""Flask CLI commands for the Reminders project."""

import logging
from datetime import datetime, timedelta

import click
from flask.cli import with_appcontext

from app import db

logger = logging.getLogger(__name__)


def init_app(app):
    app.cli.add_command(reminders_cli)


@click.group(name="reminders")
def reminders_cli():
    """Reminders project commands."""
    pass


@reminders_cli.command("send")
@with_appcontext
def send_command():
    """
    Send all due reminders within the ±7 minute window.
    Intended to be run every 5 minutes via a Render Cron Job.
    """
    from app.projects.reminders.models import Reminder
    from app.projects.reminders.email import send_reminder_email

    now = datetime.utcnow()
    window_start = now - timedelta(minutes=7)
    window_end = now + timedelta(minutes=7)

    due_reminders = (
        Reminder.query
        .join(Reminder.user)
        .filter(
            Reminder.remind_at >= window_start,
            Reminder.remind_at <= window_end,
            Reminder.sent_at.is_(None),
        )
        .all()
    )

    # Filter out users with no credits in Python to avoid a join complexity
    eligible = [r for r in due_reminders if (r.user.credits or 0) >= 1]
    skipped_no_credits = len(due_reminders) - len(eligible)

    sent = 0
    failed = 0

    for reminder in eligible:
        try:
            send_reminder_email(reminder)
            reminder.sent_at = datetime.utcnow()
            reminder.user.credits = (reminder.user.credits or 0) - 1
            db.session.commit()
            sent += 1
            logger.info(f"Sent reminder {reminder.id} to {reminder.user.email}")
        except Exception as e:
            db.session.rollback()
            failed += 1
            logger.error(f"Failed to send reminder {reminder.id}: {e}")

    click.echo(
        f"Reminders send complete: {sent} sent, {failed} failed, "
        f"{skipped_no_credits} skipped (no credits)."
    )
