"""
Logging utilities for tracking user activity across the site.
"""

from flask_login import current_user
from app.models import LogEntry
from app import db


def log_project_visit(project_name, project_display_name=None):
    """
    Log a visit to a project/page.
    
    Args:
        project_name (str): The project identifier (e.g., 'mastermind', 'simon_says')
        project_display_name (str, optional): Human-readable name for the description.
                                              Defaults to project_name if not provided.
    """
    display_name = project_display_name or project_name
    
    if current_user.is_authenticated:
        user_desc = f"User {current_user.email}"
        actor_id = current_user.id
    else:
        user_desc = "Anonymous user"
        actor_id = None
    
    log_entry = LogEntry(
        project=project_name,
        category='Visit',
        actor_id=actor_id,
        description=f"{user_desc} visited {display_name}"
    )
    db.session.add(log_entry)
    db.session.commit()


