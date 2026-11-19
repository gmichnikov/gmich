"""Text shown for a visit in the list."""

from app.projects.been.activities import activity_label
from app.projects.been.parsing import format_when


def visit_title(visit):
    if visit.place is not None:
        return visit.place.name
    return "Untitled place"


def visit_meta(visit):
    parts = []
    if visit.place is not None:
        location = visit.place.location_label()
        if location:
            parts.append(location)
        if visit.place.kind == "region":
            parts.append("Region")
    when = format_when(visit.visited_on, visit.date_precision)
    if when:
        parts.append(when)
    activity = activity_label(visit.activity)
    if activity:
        parts.append(activity)
    return " · ".join(parts)
