from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.core.admin import admin_required
from app.projects.japan_recs.photos import (
    ALLOWED_CITIES,
    build_photo_path,
    delete_photo,
    extension_for_upload,
    list_photos,
    photo_key_snippet,
    resolve_photo_url,
    upload_photo,
)
from app.utils.logging import log_project_visit

japan_recs_bp = Blueprint(
    "japan_recs",
    __name__,
    url_prefix="/japan-recs",
    template_folder="templates",
    static_folder="static",
    static_url_path="/japan-recs/static",
)


@japan_recs_bp.route("/")
def index():
    """Japan Recs hub — links to city maps."""
    log_project_visit("japan_recs", "Japan Recs")
    return render_template("japan_recs/index.html")


@japan_recs_bp.route("/kyoto")
def kyoto():
    """Kyoto trip map — public, no login or database."""
    log_project_visit("japan_recs", "Kyoto Map")
    return render_template("japan_recs/kyoto.html")


@japan_recs_bp.route("/tokyo")
def tokyo():
    """Tokyo trip map — public, no login or database."""
    log_project_visit("japan_recs", "Tokyo Map")
    return render_template("japan_recs/tokyo.html")


@japan_recs_bp.route("/photos/<path:filename>")
def photo(filename):
    """Redirect to a presigned R2 URL for a Japan Recs photo."""
    url = resolve_photo_url(filename)
    if not url:
        abort(404)
    return redirect(url, code=302)


@japan_recs_bp.route("/admin/photos", methods=["GET", "POST"])
@login_required
@admin_required
def admin_photos():
    """Upload and manage Japan Recs photos in R2."""
    if request.method == "POST":
        action = request.form.get("action", "upload")
        try:
            if action == "delete":
                path = request.form.get("photo_path", "")
                delete_photo(path)
                flash(f"Deleted {path}.", "success")
            else:
                city = request.form.get("city", "")
                slug = request.form.get("filename", "")
                photo_file = request.files.get("photo")
                if not photo_file or not photo_file.filename:
                    raise ValueError("Choose a photo file to upload.")
                extension = extension_for_upload(photo_file)
                if not extension:
                    raise ValueError("Upload a JPG, PNG, or WebP image.")
                path = build_photo_path(city, slug, extension)
                if not path:
                    raise ValueError(
                        "Pick Kyoto or Tokyo and enter a slug like bamboo-forest."
                    )
                uploaded_path = upload_photo(path, photo_file)
                flash(
                    f"Uploaded {uploaded_path}. Add this to the place in JS: "
                    f"{photo_key_snippet(uploaded_path)}",
                    "success",
                )
        except ValueError as exc:
            flash(str(exc), "error")

        return redirect(url_for("japan_recs.admin_photos"))

    photos = list_photos()
    return render_template(
        "japan_recs/admin_photos.html",
        photos=photos,
        cities=ALLOWED_CITIES,
    )
