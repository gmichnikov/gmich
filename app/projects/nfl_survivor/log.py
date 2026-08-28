"""NFL Survivor activity logging."""

from flask_login import current_user

from app import db
from app.models import LogEntry

PROJECT = "nfl_survivor"
_UNSET = object()


def log_nfl_survivor(category, description, actor_id=_UNSET):
    """Write a LogEntry for project nfl_survivor."""
    if actor_id is _UNSET:
        actor_id = current_user.id if current_user.is_authenticated else None
    db.session.add(
        LogEntry(
            project=PROJECT,
            category=category,
            actor_id=actor_id,
            description=description,
        )
    )
