from datetime import datetime

from flask import abort, Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import csrf, db
from app.projects.travel_log.models import TlogCollection, TlogEntry, TlogEntryPhoto
from app.projects.travel_log.services.r2 import (
    generate_photo_key,
    generate_presigned_download_url,
    generate_presigned_upload_url,
)
from app.projects.travel_log.utils import get_visited_date_default
from app.projects.travel_log.services.places import (
    CATEGORY_TYPES,
    search_nearby,
    search_text,
)
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


def _get_default_collection_id(collections):
    """Most recently used collection: last entry's collection, else most recently modified."""
    last_entry = TlogEntry.query.filter_by(user_id=current_user.id).order_by(TlogEntry.updated_at.desc()).first()
    if last_entry:
        return last_entry.collection_id
    return collections[0].id if collections else None


def get_photo_view_url(photo):
    """Return presigned download URL for a photo. Pass to templates when rendering entry."""
    return generate_presigned_download_url(photo.r2_key) if photo else None


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
    """Log Place page — Browse/Search nearby places, create entry."""
    collections = _get_user_collections()
    if not collections:
        flash("Create a collection first to log places.", "error")
        return redirect(url_for("travel_log.index"))

    # Optional pre-select from query param (e.g. from collection page)
    requested_id = request.args.get("collection_id", type=int)
    if requested_id and any(c.id == requested_id for c in collections):
        default_collection_id = requested_id
    else:
        default_collection_id = _get_default_collection_id(collections)

    return render_template(
        "travel_log/log.html",
        collections=collections,
        default_collection_id=default_collection_id,
    )


@travel_log_bp.route("/api/places/nearby", methods=["POST"])
@csrf.exempt
@login_required
def api_places_nearby():
    """JSON: { lat, lng, radius?, category? } → list of places."""
    data = request.get_json(silent=True) or {}
    lat = data.get("lat")
    lng = data.get("lng")
    if lat is None or lng is None:
        return jsonify({"error": "lat and lng required"}), 400
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lng must be numbers"}), 400
    radius = data.get("radius")
    radius_m = int(radius) if radius is not None else 200
    category = data.get("category")  # "food", "shopping", "attractions", "other" or null
    included_types = CATEGORY_TYPES.get(category) if category else None
    try:
        places = search_nearby(lat, lng, radius_m=radius_m, included_types=included_types)
    except Exception as e:
        return jsonify({"error": "Could not fetch nearby places. Please try again.", "places": []}), 500
    return jsonify({"places": places})


@travel_log_bp.route("/api/places/search", methods=["POST"])
@csrf.exempt
@login_required
def api_places_search():
    """JSON: { query, lat?, lng? } → list of places. lat/lng optional (GPS-failure flow)."""
    data = request.get_json(silent=True) or {}
    query = data.get("query") or ""
    if not query.strip():
        return jsonify({"error": "query required"}), 400
    lat = data.get("lat")
    lng = data.get("lng")
    if lat is not None and lng is not None:
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            lat, lng = None, None
    try:
        places = search_text(query, lat=lat, lng=lng)
    except Exception as e:
        return jsonify({"error": "Could not search places. Please try again.", "places": []}), 500
    return jsonify({"places": places})


@travel_log_bp.route("/entries/create", methods=["POST"])
@login_required
def entries_create():
    """Create entry from Log Place form. Expects form or JSON; returns JSON with redirect."""
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form

    collection_id = data.get("collection_id")
    user_name = (data.get("user_name") or "").strip()
    if not collection_id or not user_name:
        return jsonify({"error": "collection_id and user_name required"}), 400

    collection = TlogCollection.query.filter_by(id=collection_id, user_id=current_user.id).first()
    if not collection:
        return jsonify({"error": "Collection not found"}), 404

    place_id = data.get("place_id") or None
    lat = data.get("lat")
    lng = data.get("lng")
    if lat is not None and lng is not None:
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            lat, lng = None, None
    else:
        lat, lng = None, None

    visited_date_str = data.get("visited_date")
    if visited_date_str:
        try:
            from datetime import datetime as dt
            visited_date = dt.strptime(visited_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            visited_date = get_visited_date_default(lat, lng) if (lat and lng) else datetime.utcnow().date()
    else:
        visited_date = get_visited_date_default(lat, lng) if (lat and lng) else datetime.utcnow().date()

    now = datetime.utcnow()
    entry = TlogEntry(
        user_id=current_user.id,
        collection_id=collection.id,
        place_id=place_id,
        lat=lat,
        lng=lng,
        user_name=user_name,
        user_address=(data.get("user_address") or "").strip() or None,
        notes=None,
        visited_date=visited_date,
    )
    db.session.add(entry)
    collection.last_modified = now
    db.session.commit()

    redirect_url = url_for("travel_log.collections_show", id=collection.id)
    return jsonify({"redirect": redirect_url})


@travel_log_bp.route("/entries/<int:id>")
@login_required
def entries_edit(id):
    """View/edit entry."""
    entry = TlogEntry.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    return render_template(
        "travel_log/entries/edit.html",
        entry=entry,
        get_photo_view_url=get_photo_view_url,
    )


@travel_log_bp.route("/entries/<int:id>/update", methods=["POST"])
@login_required
def entries_update(id):
    """Update entry: user_name, user_address, notes, visited_date."""
    entry = TlogEntry.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    user_name = (request.form.get("user_name") or "").strip()
    if not user_name:
        flash("Place name is required.", "error")
        return redirect(url_for("travel_log.entries_edit", id=id))

    entry.user_name = user_name
    entry.user_address = (request.form.get("user_address") or "").strip() or None
    entry.notes = (request.form.get("notes") or "").strip() or None
    visited_date_str = request.form.get("visited_date")
    if visited_date_str:
        try:
            from datetime import datetime as dt
            entry.visited_date = dt.strptime(visited_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass  # keep existing if parse fails
    entry.updated_at = datetime.utcnow()
    entry.collection.last_modified = datetime.utcnow()
    db.session.commit()

    flash("Entry updated.", "success")
    return redirect(url_for("travel_log.collections_show", id=entry.collection_id))


@travel_log_bp.route("/entries/<int:id>/delete", methods=["POST"])
@login_required
def entries_delete(id):
    """Delete entry (cascade photos)."""
    entry = TlogEntry.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    collection_id = entry.collection_id
    collection = entry.collection
    user_name = entry.user_name

    db.session.delete(entry)
    collection.last_modified = datetime.utcnow()
    db.session.commit()

    flash(f'"{user_name}" deleted.', "success")
    return redirect(url_for("travel_log.collections_show", id=collection_id))


# --- Photo upload API ---


@travel_log_bp.route("/api/photos/presign", methods=["POST"])
@csrf.exempt
@login_required
def api_photos_presign():
    """JSON: { entry_id } → { upload_url, key }. Verify entry belongs to user."""
    data = request.get_json(silent=True) or {}
    entry_id = data.get("entry_id")
    if entry_id is None:
        return jsonify({"error": "entry_id required"}), 400

    entry = TlogEntry.query.filter_by(id=entry_id, user_id=current_user.id).first()
    if not entry:
        return jsonify({"error": "Entry not found"}), 404

    key = generate_photo_key(current_user.id, entry_id)
    upload_url, _ = generate_presigned_upload_url(key, content_type="image/jpeg")
    if not upload_url:
        return jsonify({"error": "Failed to generate upload URL"}), 500

    return jsonify({"upload_url": upload_url, "key": key})


@travel_log_bp.route("/api/photos/confirm", methods=["POST"])
@csrf.exempt
@login_required
def api_photos_confirm():
    """JSON: { entry_id, key } → { success, photo_id?, view_url? }. Create TlogEntryPhoto, update timestamps."""
    data = request.get_json(silent=True) or {}
    entry_id = data.get("entry_id")
    key = data.get("key")
    if entry_id is None or not key:
        return jsonify({"error": "entry_id and key required"}), 400

    entry = TlogEntry.query.filter_by(id=entry_id, user_id=current_user.id).first()
    if not entry:
        return jsonify({"error": "Entry not found"}), 404

    max_order = (
        TlogEntryPhoto.query.filter_by(entry_id=entry_id)
        .with_entities(db.func.max(TlogEntryPhoto.sort_order))
        .scalar()
    )
    sort_order = (max_order or 0) + 1

    photo = TlogEntryPhoto(entry_id=entry_id, r2_key=key, sort_order=sort_order)
    db.session.add(photo)
    entry.updated_at = datetime.utcnow()
    entry.collection.last_modified = datetime.utcnow()
    db.session.commit()

    view_url = get_photo_view_url(photo)
    return jsonify({"success": True, "photo_id": photo.id, "view_url": view_url})


@travel_log_bp.route("/entries/<int:id>/photos/<int:photo_id>/delete", methods=["POST"])
@login_required
def entries_photo_delete(id, photo_id):
    """Delete photo. Verify photo's entry belongs to user. Redirect to entries_edit."""
    photo = TlogEntryPhoto.query.filter_by(id=photo_id).first_or_404()
    if photo.entry.user_id != current_user.id:
        abort(404)
    entry = photo.entry
    collection = entry.collection

    db.session.delete(photo)
    entry.updated_at = datetime.utcnow()
    collection.last_modified = datetime.utcnow()
    db.session.commit()

    flash("Photo removed.", "success")
    return redirect(url_for("travel_log.entries_edit", id=id))
