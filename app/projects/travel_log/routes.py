import random
from datetime import datetime

from flask import abort, Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func
from flask_login import current_user, login_required

from app import csrf, db
from app.models import User
from app.projects.travel_log.models import (
    TlogCollection,
    TlogCollectionMember,
    TlogEntry,
    TlogEntryPhoto,
    TlogTag,
)
from app.projects.travel_log.permissions import (
    ROLE_EDITOR,
    can_edit_collection,
    can_edit_entry,
    can_manage_collection_settings,
    can_manage_sharing,
    get_collection_for_access,
    get_entry_for_access,
    is_collection_owner,
    normalize_invite_email,
)
from app.projects.travel_log.tag_inference import infer_tag_names_from_google_place
from app.projects.travel_log.utils import parse_place_detail_from_client
from app.projects.travel_log.services.r2 import (
    generate_photo_key,
    generate_presigned_download_url,
    generate_presigned_upload_url,
)
from app.projects.travel_log.utils import contrast_text_color, get_visited_date_default
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


@travel_log_bp.app_template_filter("tlog_contrast_text")
def tlog_contrast_text_filter(bg_hex):
    """Return 'light' or 'dark' for tag text contrast."""
    return contrast_text_color(bg_hex)


def _owned_collections_query():
    return TlogCollection.query.filter_by(user_id=current_user.id).order_by(TlogCollection.last_modified.desc())


def _get_user_collections():
    """Collections the current user owns (ordered by last_modified DESC)."""
    return _owned_collections_query().all()


def _shared_collections_with_owners():
    """(TlogCollection, owner User) for collections shared as editor."""
    return (
        db.session.query(TlogCollection, User)
        .join(TlogCollectionMember, TlogCollectionMember.collection_id == TlogCollection.id)
        .join(User, User.id == TlogCollection.user_id)
        .filter(
            TlogCollectionMember.user_id == current_user.id,
            TlogCollectionMember.role == ROLE_EDITOR,
            TlogCollection.user_id != current_user.id,
        )
        .order_by(TlogCollection.last_modified.desc())
        .all()
    )


def _log_collection_items():
    """Owned + shared rows for Log Place: { collection, shared, owner_label }."""
    items = []
    for c in _owned_collections_query().all():
        items.append({"collection": c, "shared": False, "owner_label": None})
    for c, owner in _shared_collections_with_owners():
        label = (owner.short_name or owner.full_name or owner.email or "Owner").strip()
        items.append({"collection": c, "shared": True, "owner_label": label})
    return items


def _parse_invite_emails(raw: str) -> list[str]:
    if not raw or not isinstance(raw, str):
        return []
    chunks = raw.replace(",", "\n").split("\n")
    seen: set[str] = set()
    out: list[str] = []
    for line in chunks:
        for part in line.split(","):
            n = normalize_invite_email(part)
            if n and n not in seen:
                seen.add(n)
                out.append(n)
    return out


def _default_log_collection_id(items):
    """Last collection where current user created an entry, else first in list."""
    if not items:
        return None
    ids = [i["collection"].id for i in items]
    last_entry = (
        TlogEntry.query.filter(
            TlogEntry.collection_id.in_(ids),
            TlogEntry.user_id == current_user.id,
        )
        .order_by(TlogEntry.updated_at.desc())
        .first()
    )
    if last_entry:
        return last_entry.collection_id
    return items[0]["collection"].id


def get_photo_view_url(photo):
    """Return presigned download URL for a photo. Pass to templates when rendering entry."""
    return generate_presigned_download_url(photo.r2_key) if photo else None


@travel_log_bp.route("/")
@login_required
def index():
    log_project_visit("travel_log", "Travel Log")

    owned_data = []
    for c in _owned_collections_query().all():
        owned_data.append(
            {
                "collection": c,
                "entry_count": c.entries.count(),
                "latest_entry": c.entries.first(),
            }
        )

    shared_data = []
    for c, owner in _shared_collections_with_owners():
        shared_data.append(
            {
                "collection": c,
                "entry_count": c.entries.count(),
                "latest_entry": c.entries.first(),
                "owner_name": (owner.short_name or owner.full_name or owner.email or "").strip(),
            }
        )

    return render_template(
        "travel_log/index.html",
        owned_collections=owned_data,
        shared_collections=shared_data,
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


def _parse_date(s):
    """Parse YYYY-MM-DD string to date or None."""
    if not s or not s.strip():
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@travel_log_bp.route("/collections/<int:id>")
@login_required
def collections_show(id):
    collection = get_collection_for_access(current_user, id)
    is_owner = is_collection_owner(current_user, collection)
    owner_display = None
    if not is_owner and collection.user:
        u = collection.user
        owner_display = (u.short_name or u.full_name or u.email or "").strip()
    entries = collection.entries.order_by(TlogEntry.updated_at.desc()).all()

    # Unique dates in collection (for date chip filter UI), sorted
    collection_dates = []
    # Tags used in this collection (for tag chip filter UI)
    collection_tags = []
    if entries:
        seen_dates = set()
        seen_tag_ids = set()
        for e in entries:
            if e.visited_date and e.visited_date not in seen_dates:
                seen_dates.add(e.visited_date)
                collection_dates.append((e.visited_date.isoformat(), e.visited_date.strftime("%b %d, %Y")))
            for tag in e.tags:
                if tag.id not in seen_tag_ids:
                    seen_tag_ids.add(tag.id)
                    collection_tags.append(tag)
        collection_dates.sort(key=lambda x: x[0])
        collection_tags.sort(key=lambda t: t.name)

    # Date range for the range modal (hidden for now)
    date_range = (
        db.session.query(func.min(TlogEntry.visited_date), func.max(TlogEntry.visited_date))
        .filter(TlogEntry.collection_id == collection.id)
        .first()
    )
    collection_date_min = date_range[0].isoformat() if date_range and date_range[0] else None
    collection_date_max = date_range[1].isoformat() if date_range and date_range[1] else None

    # Attach random thumbnail photo and all photo URLs per entry (for lightbox)
    for entry in entries:
        photos = entry.photos.all()
        if photos:
            entry.random_photo = random.choice(photos)
            entry.all_photo_urls = [get_photo_view_url(p) for p in photos]
        else:
            entry.random_photo = None
            entry.all_photo_urls = []

    return render_template(
        "travel_log/collections/show.html",
        collection=collection,
        entries=entries,
        get_photo_view_url=get_photo_view_url,
        collection_dates=collection_dates,
        collection_tags=collection_tags,
        collection_date_min=collection_date_min,
        collection_date_max=collection_date_max,
        is_owner=is_owner,
        owner_display=owner_display,
    )


@travel_log_bp.route("/collections/<int:id>/edit", methods=["GET"])
@login_required
def collections_edit(id):
    collection = TlogCollection.query.get_or_404(id)
    if not can_manage_collection_settings(current_user, collection):
        abort(404)
    entry_count = collection.entries.count()
    return render_template(
        "travel_log/collections/edit.html",
        collection=collection,
        entry_count=entry_count,
    )


@travel_log_bp.route("/collections/<int:id>/update", methods=["POST"])
@login_required
def collections_update(id):
    collection = TlogCollection.query.get_or_404(id)
    if not can_manage_collection_settings(current_user, collection):
        abort(404)
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
    collection = TlogCollection.query.get_or_404(id)
    if not can_manage_collection_settings(current_user, collection):
        abort(404)
    entry_count = collection.entries.count()
    name = collection.name

    db.session.delete(collection)
    db.session.commit()

    flash(f'Collection "{name}" and {entry_count} entries deleted.', "success")
    return redirect(url_for("travel_log.index"))


@travel_log_bp.route("/collections/<int:id>/sharing/members", methods=["GET"])
@login_required
def collection_sharing_members(id):
    """JSON: owner + editors for share modal."""
    collection = TlogCollection.query.get_or_404(id)
    if not can_manage_sharing(current_user, collection):
        return jsonify({"error": "Forbidden"}), 403
    owner = collection.user
    editors = []
    for m in collection.memberships.order_by(TlogCollectionMember.created_at).all():
        u = m.user
        editors.append(
            {
                "user_id": u.id,
                "email": u.email,
                "display_name": (u.short_name or u.full_name or u.email or "").strip(),
            }
        )
    return jsonify(
        {
            "owner": {
                "user_id": owner.id,
                "email": owner.email,
                "display_name": (owner.short_name or owner.full_name or owner.email or "").strip(),
            },
            "editors": editors,
        }
    )


@travel_log_bp.route("/collections/<int:id>/sharing/invite", methods=["POST"])
@csrf.exempt
@login_required
def collection_sharing_invite(id):
    """JSON: { emails: string } — add editors by email (registered users only)."""
    collection = TlogCollection.query.get_or_404(id)
    if not can_manage_sharing(current_user, collection):
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    emails_str = data.get("emails") or ""
    added = []
    skipped_unknown = []
    already_access = []
    skipped_owner = []
    owner_email = normalize_invite_email(collection.user.email or "")
    for em in _parse_invite_emails(emails_str):
        if em == owner_email:
            skipped_owner.append(em)
            continue
        target = User.query.filter(func.lower(User.email) == em).first()
        if not target:
            skipped_unknown.append(em)
            continue
        if target.id == collection.user_id:
            skipped_owner.append(em)
            continue
        existing = TlogCollectionMember.query.filter_by(collection_id=collection.id, user_id=target.id).first()
        if existing:
            already_access.append(em)
            continue
        db.session.add(
            TlogCollectionMember(collection_id=collection.id, user_id=target.id, role=ROLE_EDITOR)
        )
        added.append(em)
    db.session.commit()
    return jsonify(
        {
            "added": added,
            "skipped_unknown": skipped_unknown,
            "already_access": already_access,
            "skipped_owner": skipped_owner,
        }
    )


@travel_log_bp.route("/collections/<int:id>/sharing/remove", methods=["POST"])
@csrf.exempt
@login_required
def collection_sharing_remove(id):
    """JSON: { user_id: int } — remove an editor."""
    collection = TlogCollection.query.get_or_404(id)
    if not can_manage_sharing(current_user, collection):
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    uid = data.get("user_id")
    if uid is None:
        return jsonify({"error": "user_id required"}), 400
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return jsonify({"error": "user_id invalid"}), 400
    if uid == collection.user_id:
        return jsonify({"error": "Cannot remove owner"}), 400
    m = TlogCollectionMember.query.filter_by(collection_id=collection.id, user_id=uid).first()
    if not m:
        return jsonify({"error": "Not a member"}), 404
    db.session.delete(m)
    db.session.commit()
    return jsonify({"success": True})


@travel_log_bp.route("/log")
@login_required
def log():
    """Log Place page — Browse/Search nearby places, create entry."""
    log_collections = _log_collection_items()
    if not log_collections:
        flash("Create a collection or get invited to one to log places.", "error")
        return redirect(url_for("travel_log.index"))

    # Optional pre-select from query param (e.g. from collection page)
    requested_id = request.args.get("collection_id", type=int)
    ids = {i["collection"].id for i in log_collections}
    if requested_id and requested_id in ids:
        default_collection_id = requested_id
    else:
        default_collection_id = _default_log_collection_id(log_collections)

    log_owned = [i for i in log_collections if not i["shared"]]
    log_shared = [i for i in log_collections if i["shared"]]

    global_tags = TlogTag.query.filter_by(scope="global").order_by(TlogTag.name).all()

    return render_template(
        "travel_log/log.html",
        log_collections_owned=log_owned,
        log_collections_shared=log_shared,
        default_collection_id=default_collection_id,
        global_tags=global_tags,
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


@travel_log_bp.route("/api/tags/suggest", methods=["POST"])
@csrf.exempt
@login_required
def api_tags_suggest():
    """JSON: { types: string[], primary_type?: string } → { tag_ids: int[] } for Log Place UI."""
    data = request.get_json(silent=True) or {}
    types = data.get("types") or []
    if not isinstance(types, list):
        types = []
    types = [str(t).strip() for t in types if t is not None and str(t).strip()]
    primary_type = data.get("primary_type")
    if primary_type is not None and not isinstance(primary_type, str):
        primary_type = str(primary_type) if primary_type else None
    inferred_names = infer_tag_names_from_google_place(types, primary_type)
    if not inferred_names:
        return jsonify({"tag_ids": []})
    tags = (
        TlogTag.query.filter_by(scope="global")
        .filter(TlogTag.name.in_(inferred_names))
        .all()
    )
    return jsonify({"tag_ids": [t.id for t in tags]})


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

    try:
        cid = int(collection_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Collection not found"}), 404
    collection = TlogCollection.query.get(cid)
    if not collection or not can_edit_collection(current_user, collection):
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

    place_detail = parse_place_detail_from_client(data)

    def _tags_for_new_entry():
        """Explicit tag_ids when provided; else infer from types (JSON only). Form uses checkboxes only."""
        if request.is_json:
            raw = data.get("tag_ids")
            if raw is not None:
                if not isinstance(raw, list):
                    return []
                try:
                    ids = [int(x) for x in raw]
                except (TypeError, ValueError):
                    return []
                valid = {t.id for t in TlogTag.query.filter_by(scope="global").filter(TlogTag.id.in_(ids)).all()}
                return list(TlogTag.query.filter(TlogTag.id.in_(valid)).all())
            google_types = data.get("google_types")
            gt_list = [str(t) for t in google_types] if isinstance(google_types, list) else []
            names = infer_tag_names_from_google_place(gt_list, place_detail.get("primary_type"))
            if not names:
                return []
            return (
                TlogTag.query.filter_by(scope="global")
                .filter(TlogTag.name.in_(names))
                .all()
            )

        tag_ids = request.form.getlist("tag_ids", type=int)
        valid_ids = {t.id for t in TlogTag.query.filter_by(scope="global").filter(TlogTag.id.in_(tag_ids)).all()}
        return list(TlogTag.query.filter(TlogTag.id.in_(valid_ids)).all())

    entry_tags = _tags_for_new_entry()

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
        **place_detail,
    )
    db.session.add(entry)
    db.session.flush()
    entry.tags = entry_tags
    collection.last_modified = now
    db.session.commit()

    redirect_url = url_for("travel_log.collections_show", id=collection.id)
    return jsonify({"redirect": redirect_url})


@travel_log_bp.route("/entries/<int:id>")
@login_required
def entries_edit(id):
    """View/edit entry."""
    entry = get_entry_for_access(current_user, id)
    global_tags = TlogTag.query.filter_by(scope="global").order_by(TlogTag.name).all()
    return render_template(
        "travel_log/entries/edit.html",
        entry=entry,
        global_tags=global_tags,
        get_photo_view_url=get_photo_view_url,
    )


@travel_log_bp.route("/entries/<int:id>/update", methods=["POST"])
@login_required
def entries_update(id):
    """Update entry: user_name, user_address, place detail fields, notes, visited_date, tags."""
    entry = get_entry_for_access(current_user, id)
    user_name = (request.form.get("user_name") or "").strip()
    if not user_name:
        flash("Place name is required.", "error")
        return redirect(url_for("travel_log.entries_edit", id=id))

    entry.user_name = user_name
    entry.user_address = (request.form.get("user_address") or "").strip() or None
    entry.notes = (request.form.get("notes") or "").strip() or None

    pd = parse_place_detail_from_client(request.form)
    entry.primary_type = pd["primary_type"]
    entry.primary_type_display_name = pd["primary_type_display_name"]
    entry.short_formatted_address = pd["short_formatted_address"]
    entry.addr_locality = pd["addr_locality"]
    entry.addr_admin_area_1 = pd["addr_admin_area_1"]
    entry.addr_admin_area_2 = pd["addr_admin_area_2"]
    entry.addr_admin_area_3 = pd["addr_admin_area_3"]
    entry.addr_country_code = pd["addr_country_code"]
    visited_date_str = request.form.get("visited_date")
    if visited_date_str:
        try:
            from datetime import datetime as dt
            entry.visited_date = dt.strptime(visited_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass  # keep existing if parse fails

    # Tags: getlist for multi-select
    tag_ids = request.form.getlist("tag_ids", type=int)
    valid_tag_ids = {t.id for t in TlogTag.query.filter_by(scope="global").filter(TlogTag.id.in_(tag_ids)).all()}
    entry.tags = [t for t in entry.tags if t.scope != "global"] + list(TlogTag.query.filter(TlogTag.id.in_(valid_tag_ids)).all())
    # Simpler: replace with selected global tags only (for now we only have global)
    entry.tags = list(TlogTag.query.filter(TlogTag.id.in_(valid_tag_ids)).all())

    entry.updated_at = datetime.utcnow()
    entry.collection.last_modified = datetime.utcnow()
    db.session.commit()

    flash("Entry updated.", "success")
    return redirect(url_for("travel_log.collections_show", id=entry.collection_id))


@travel_log_bp.route("/entries/<int:id>/delete", methods=["POST"])
@login_required
def entries_delete(id):
    """Delete entry (cascade photos)."""
    entry = get_entry_for_access(current_user, id)
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

    entry = TlogEntry.query.get(entry_id)
    if not entry or not can_edit_entry(current_user, entry):
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

    entry = TlogEntry.query.get(entry_id)
    if not entry or not can_edit_entry(current_user, entry):
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
    if not can_edit_entry(current_user, photo.entry):
        abort(404)
    entry = photo.entry
    collection = entry.collection

    db.session.delete(photo)
    entry.updated_at = datetime.utcnow()
    collection.last_modified = datetime.utcnow()
    db.session.commit()

    flash("Photo removed.", "success")
    return redirect(url_for("travel_log.entries_edit", id=id))
