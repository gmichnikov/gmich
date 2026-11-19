"""What you did at a place. A value here marks the visit as water."""

from app.projects.been.parsing import VisitInputError

ACTIVITIES = (
    ("swam", "Swam"),
    ("boated", "Boated"),
    ("ferry", "Ferry"),
    ("dived", "Dived"),
    ("sailed", "Sailed"),
)

ACTIVITY_LABELS = dict(ACTIVITIES)


def activity_label(code):
    if not code:
        return ""
    return ACTIVITY_LABELS.get(code, code)


def clean_activity(raw):
    code = (raw or "").strip().lower()
    if not code:
        return None
    if code not in ACTIVITY_LABELS:
        raise VisitInputError("Pick a water activity from the list.")
    return code
