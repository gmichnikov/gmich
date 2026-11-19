"""Create and update a user's places and visits."""

from sqlalchemy.exc import IntegrityError

from app import db
from app.projects.been.models import BeenPlace, BeenVisit
from app.projects.been.parsing import VisitInputError, parse_when
from app.projects.been.places import clean_place
from app.projects.been.water import clean_activity, clean_water_slug


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


def add_visit(user_id, *, place, water_slug, activity, when, notes):
    visited_on, precision = parse_when(when)
    water_slug = clean_water_slug(water_slug)
    activity = clean_activity(activity)
    notes = _clean_notes(notes)
    if place is None and not water_slug:
        raise VisitInputError("Add a place or a body of water.")
    if activity and not water_slug:
        raise VisitInputError("Pick a body of water for that activity.")
    place_row = None
    if place is not None:
        place_row = find_or_create_place(user_id, clean_place(place))
    visit = BeenVisit(
        user_id=user_id,
        place=place_row,
        water_slug=water_slug,
        activity=activity,
        visited_on=visited_on,
        date_precision=precision,
        notes=notes,
    )
    db.session.add(visit)
    db.session.flush()
    return visit


def update_visit(visit, *, water_slug, activity, when, notes):
    visited_on, precision = parse_when(when)
    water_slug = clean_water_slug(water_slug)
    activity = clean_activity(activity)
    notes = _clean_notes(notes)
    if visit.place_id is None and not water_slug:
        raise VisitInputError("This visit needs a body of water.")
    if activity and not water_slug:
        raise VisitInputError("Pick a body of water for that activity.")
    visit.water_slug = water_slug
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
