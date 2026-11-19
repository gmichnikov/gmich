"""Text shown for a visit in the list."""

from app.projects.been.parsing import format_when
from app.projects.been.water import activity_label, water_name


def visit_title(visit):
    if visit.place is not None:
        return visit.place.name
    return water_name(visit.water_slug)


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
    if visit.water_slug and visit.place is not None:
        water = water_name(visit.water_slug)
        activity = activity_label(visit.activity)
        parts.append(f"{activity} · {water}" if activity else water)
    elif visit.activity:
        parts.append(activity_label(visit.activity))
    return " · ".join(parts)
