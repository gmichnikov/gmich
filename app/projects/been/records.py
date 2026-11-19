"""Create and update a user's places and visits."""

from sqlalchemy.exc import IntegrityError

from app import db
from app.projects.been.models import BeenPlace, BeenVisit
from app.projects.been.parsing import VisitInputError, parse_when
from app.projects.been.places import clean_place
from app.projects.been.activities import clean_activity


def _clean_notes(raw):
    notes = (raw or "").strip()
    if not notes:
        return None
    return notes[:4000]


def find_or_create_place(user_id, place):
    osm_type = place.get("osm_type")
    osm_id = place.get("osm_id")
    if osm_type and osm_id is not None:
        existing = BeenPlace.query.filter_by(
            user_id=user_id,
            osm_type=osm_type,
            osm_id=osm_id,
        ).first()
        if existing:
            return existing
    row = BeenPlace(
        user_id=user_id,
        name=place["name"],
        kind=place["kind"],
        lat=place["lat"],
        lng=place["lng"],
        country_code=place.get("country_code"),
        country_name=place.get("country_name"),
        region_name=place.get("region_name"),
        city=place.get("city"),
        osm_type=osm_type,
        osm_id=osm_id,
        osm_key=place.get("osm_key"),
        osm_value=place.get("osm_value"),
    )
    try:
        with db.session.begin_nested():
            db.session.add(row)
            db.session.flush()
    except IntegrityError:
        existing = BeenPlace.query.filter_by(
            user_id=user_id,
            osm_type=osm_type,
            osm_id=osm_id,
        ).first()
        if existing:
            return existing
        raise
    return row


def add_visit(user_id, *, place, activity, when, notes):
    visited_on, precision = parse_when(when)
    activity = clean_activity(activity)
    notes = _clean_notes(notes)
    if place is None:
        raise VisitInputError("Choose a place from the search results.")
    place_row = find_or_create_place(user_id, clean_place(place))
    visit = BeenVisit(
        user_id=user_id,
        place=place_row,
        activity=activity,
        visited_on=visited_on,
        date_precision=precision,
        notes=notes,
    )
    db.session.add(visit)
    db.session.flush()
    return visit


def update_visit(visit, *, activity, when, notes):
    visited_on, precision = parse_when(when)
    activity = clean_activity(activity)
    notes = _clean_notes(notes)
    visit.activity = activity
    visit.visited_on = visited_on
    visit.date_precision = precision
    visit.notes = notes
    db.session.flush()
    return visit


def delete_visit(visit):
    place = visit.place
    db.session.delete(visit)
    db.session.flush()
    if place is not None and place.visits.count() == 0:
        db.session.delete(place)
