"""Private pages for Where I've Been. Sharing is a later step."""

import json
import time

import requests
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app import db
from app.projects.been.models import BeenPlace, BeenVisit
from app.projects.been.parsing import VisitInputError, when_input_value
from app.projects.been.places import build_paste_preview, search_places
from app.projects.been.present import visit_meta, visit_title
from app.projects.been.activities import ACTIVITIES
from app.projects.been.records import add_visit, delete_visit, update_visit
from app.utils.logging import log_project_visit

been_bp = Blueprint(
    "been",
    __name__,
    url_prefix="/been",
    template_folder="templates",
    static_folder="static",
    static_url_path="/been/static",
)

_PLACE_FORM_KEYS = (
    "name",
    "kind",
    "lat",
    "lng",
    "country_code",
    "country_name",
    "region_name",
    "city",
    "osm_type",
    "osm_id",
    "osm_key",
    "osm_value",
)
_PASTE_LIMIT = 30


def _form_context(**extra):
    context = {"activities": ACTIVITIES}
    context.update(extra)
    return context


def _visit_or_404(visit_id):
    visit = (
        BeenVisit.query.options(joinedload(BeenVisit.place))
        .filter_by(id=visit_id)
        .first()
    )
    if visit is None or visit.user_id != current_user.id:
        abort(404)
    return visit


def _place_from_form(form):
    return {key: form.get(key) for key in _PLACE_FORM_KEYS}


def _paced_search():
    state = {"calls": 0}

    def _search(query, limit=1):
        if state["calls"]:
            time.sleep(0.15)
        state["calls"] += 1
        return search_places(query, limit=limit)

    return _search


def _save_message(visit):
    return f"Saved {visit_title(visit)}."


@been_bp.route("/")
@login_required
def index():
    log_project_visit("been", "Where I've Been")
    visits = (
        BeenVisit.query.options(joinedload(BeenVisit.place))
        .filter_by(user_id=current_user.id)
        .order_by(BeenVisit.visited_on.desc().nulls_last(), BeenVisit.id.desc())
        .all()
    )
    places = BeenPlace.query.filter_by(user_id=current_user.id).all()
    cards = [{"visit": visit, "title": visit_title(visit), "meta": visit_meta(visit)} for visit in visits]
    return render_template(
        "been/index.html",
        **_form_context(
            cards=cards,
            place_count=sum(1 for place in places if place.kind == "spot"),
            region_count=sum(1 for place in places if place.kind == "region"),
            country_count=len({place.country_code for place in places if place.country_code}),
            water_count=len({visit.place_id for visit in visits if visit.activity and visit.place_id}),
        ),
    )


@been_bp.route("/search")
@login_required
def search():
    try:
        results = search_places(request.args.get("q", ""))
    except requests.RequestException:
        return jsonify({"error": "Place search is unavailable right now.", "results": []}), 502
    return jsonify({"results": results})


@been_bp.route("/visits", methods=["POST"])
@login_required
def create_visit():
    try:
        visit = add_visit(
            current_user.id,
            place=_place_from_form(request.form),
            activity=request.form.get("activity"),
            when=request.form.get("when"),
            notes=request.form.get("notes"),
        )
        db.session.commit()
    except VisitInputError as exc:
        db.session.rollback()
        flash(str(exc))
        return redirect(url_for("been.index"))
    flash(_save_message(visit))
    return redirect(url_for("been.index"))


@been_bp.route("/paste", methods=["POST"])
@login_required
def paste_preview():
    preview = build_paste_preview(request.form.get("paste", ""), _paced_search(), limit=_PASTE_LIMIT)
    if not preview["rows"]:
        flash("Add one place per line.")
        return redirect(url_for("been.index"))
    return render_template(
        "been/paste_review.html",
        rows=preview["rows"],
        payload=json.dumps(preview["rows"]),
        truncated=preview["truncated"],
        limit=_PASTE_LIMIT,
    )


@been_bp.route("/paste/save", methods=["POST"])
@login_required
def paste_save():
    try:
        rows = json.loads(request.form.get("payload") or "")
    except json.JSONDecodeError:
        flash("That paste review could not be read. Paste the list again.")
        return redirect(url_for("been.index"))
    if not isinstance(rows, list) or len(rows) > _PASTE_LIMIT:
        abort(400)
    include = set(request.form.getlist("include"))
    saved = 0
    skipped = 0
    for index, row in enumerate(rows):
        if str(index) not in include or not isinstance(row, dict):
            continue
        place = row.get("place")
        if not place:
            continue
        try:
            with db.session.begin_nested():
                add_visit(
                    current_user.id,
                    place=place,
                    activity=None,
                    when=row.get("when"),
                    notes=None,
                )
            saved += 1
        except VisitInputError:
            skipped += 1
    if saved == 0:
        db.session.rollback()
        flash("Nothing was saved. Choose at least one matched place.")
        return redirect(url_for("been.index"))
    db.session.commit()
    message = f"Saved {saved} {'place' if saved == 1 else 'places'}."
    if skipped:
        message += f" Skipped {skipped}."
    flash(message)
    return redirect(url_for("been.index"))


@been_bp.route("/visits/<int:visit_id>/edit", methods=["GET", "POST"])
@login_required
def edit_visit(visit_id):
    visit = _visit_or_404(visit_id)
    if request.method == "POST":
        try:
            update_visit(
                visit,
                activity=request.form.get("activity"),
                when=request.form.get("when"),
                notes=request.form.get("notes"),
            )
            db.session.commit()
        except VisitInputError as exc:
            db.session.rollback()
            flash(str(exc))
            return redirect(url_for("been.edit_visit", visit_id=visit.id))
        flash(_save_message(visit))
        return redirect(url_for("been.index"))
    return render_template(
        "been/edit.html",
        **_form_context(
            visit=visit,
            title=visit_title(visit),
            meta=visit_meta(visit),
            when_value=when_input_value(visit.visited_on, visit.date_precision),
        ),
    )


@been_bp.route("/visits/<int:visit_id>/delete", methods=["POST"])
@login_required
def remove_visit(visit_id):
    visit = _visit_or_404(visit_id)
    title = visit_title(visit)
    delete_visit(visit)
    db.session.commit()
    flash(f"Deleted {title}.")
    return redirect(url_for("been.index"))
