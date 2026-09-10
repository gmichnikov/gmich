"""Who may use Kids AI as a parent or as a signed-in child."""

from flask_login import current_user

from app.projects.kids_ai.models import KidsAiParent


def is_allowlisted_parent(user=None):
    user = user if user is not None else current_user
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return (
        KidsAiParent.query.filter_by(user_id=user.id).first() is not None
    )
