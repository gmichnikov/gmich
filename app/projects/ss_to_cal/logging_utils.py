"""SS to Cal — activity logging (LogEntry + PostHog)."""

from app import db
from app.models import LogEntry


def log_share_not_logged_in() -> None:
    db.session.add(
        LogEntry(
            project="ss_to_cal",
            category="Share",
            actor_id=None,
            description="Share POST → outcome=not_logged_in",
        )
    )
    db.session.commit()
