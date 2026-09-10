"""Child session: a signed cookie separate from the hub Flask-Login session."""

from flask import current_app, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.projects.kids_ai.models import KidsAiChild, KidsAiParent

COOKIE_NAME = "kids_ai_child"
SALT = "kids-ai-child-session"


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt=SALT)


def child_session_token(child_id):
    return _serializer().dumps({"id": int(child_id)})


def child_id_from_cookie():
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        data = _serializer().loads(token)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return int(data.get("id"))
    except (TypeError, ValueError):
        return None


def get_current_child():
    """Return the child if the cookie is valid, enabled, and the parent is still allowlisted."""
    child_id = child_id_from_cookie()
    if child_id is None:
        return None
    child = KidsAiChild.query.get(child_id)
    if child is None or not child.enabled:
        return None
    if KidsAiParent.query.filter_by(user_id=child.parent_user_id).first() is None:
        return None
    return child


def set_child_session_cookie(response, child_id):
    response.set_cookie(
        COOKIE_NAME,
        child_session_token(child_id),
        httponly=True,
        samesite="Lax",
        secure=request.is_secure,
    )
    return response


def clear_child_session_cookie(response):
    response.delete_cookie(COOKIE_NAME)
    return response
