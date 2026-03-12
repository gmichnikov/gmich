from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.projects.travel_log.models import TlogCollection, TlogEntry
from app.utils.logging import log_project_visit

travel_log_bp = Blueprint(
    "travel_log",
    __name__,
    url_prefix="/travel-log",
    template_folder="templates",
    static_folder="static",
    static_url_path="/travel-log/static",
)


def _get_user_collections():
    """User's collections ordered by last_modified DESC."""
    return (
        TlogCollection.query.filter_by(user_id=current_user.id)
        .order_by(TlogCollection.last_modified.desc())
        .all()
    )


@travel_log_bp.route("/")
@login_required
def index():
    log_project_visit("travel_log", "Travel Log")
    collections = _get_user_collections()

    # Build preview data for each collection
    collection_data = []
    for c in collections:
        entry_count = c.entries.count()
        latest = c.entries.first()  # already ordered by updated_at desc
        collection_data.append(
            {
                "collection": c,
                "entry_count": entry_count,
                "latest_entry": latest,
            }
        )

    return render_template(
        "travel_log/index.html",
        collections=collection_data,
    )


@travel_log_bp.route("/collections/new", methods=["GET"])
@login_required
def collections_new():
    return render_template("travel_log/collections/new.html")


@travel_log_bp.route("/collections/create", methods=["POST"])
@login_required
def collections_create():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Collection name is required.", "error")
        return redirect(url_for("travel_log.collections_new"))

    now = datetime.utcnow()
    collection = TlogCollection(
        user_id=current_user.id,
        name=name,
        last_modified=now,
    )
    db.session.add(collection)
    db.session.commit()

    flash(f'Collection "{name}" created.', "success")
    return redirect(url_for("travel_log.index"))


@travel_log_bp.route("/collections/<int:id>")
@login_required
def collections_show(id):
    collection = TlogCollection.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    entries = collection.entries.order_by(TlogEntry.updated_at.desc()).all()
    return render_template(
        "travel_log/collections/show.html",
        collection=collection,
        entries=entries,
    )


@travel_log_bp.route("/collections/<int:id>/edit", methods=["GET"])
@login_required
def collections_edit(id):
    collection = TlogCollection.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    entry_count = collection.entries.count()
    return render_template(
        "travel_log/collections/edit.html",
        collection=collection,
        entry_count=entry_count,
    )


@travel_log_bp.route("/collections/<int:id>/update", methods=["POST"])
@login_required
def collections_update(id):
    collection = TlogCollection.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Collection name is required.", "error")
        return redirect(url_for("travel_log.collections_edit", id=id))

    collection.name = name
    collection.last_modified = datetime.utcnow()
    db.session.commit()

    flash("Collection updated.", "success")
    return redirect(url_for("travel_log.index"))


@travel_log_bp.route("/collections/<int:id>/delete", methods=["POST"])
@login_required
def collections_delete(id):
    collection = TlogCollection.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    entry_count = collection.entries.count()
    name = collection.name

    db.session.delete(collection)
    db.session.commit()

    flash(f'Collection "{name}" and {entry_count} entries deleted.', "success")
    return redirect(url_for("travel_log.index"))


@travel_log_bp.route("/log")
@login_required
def log():
    """Log Place page. Full implementation in Phase 4; stub for now."""
    collections = _get_user_collections()
    if not collections:
        flash("Create a collection first to log places.", "error")
        return redirect(url_for("travel_log.index"))
    flash("Log Place coming in Phase 4.", "info")
    return redirect(url_for("travel_log.collections_show", id=collections[0].id))


@travel_log_bp.route("/entries/<int:id>")
@login_required
def entries_edit(id):
    """View/edit entry. Edit form comes in Phase 5; for now read-only display."""
    entry = TlogEntry.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    return render_template("travel_log/entries/edit.html", entry=entry)
