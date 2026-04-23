from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required, current_user
from app.core.admin import admin_required

from app import db
from app.utils.logging import log_project_visit

daily_email_bp = Blueprint(
    "daily_email",
    __name__,
    url_prefix="/daily-email",
    template_folder="templates",
    static_folder="static",
    static_url_path="/daily-email/static",
)

MAX_WEATHER_LOCATIONS = 3


def _get_or_create_profile():
    from app.projects.daily_email.models import DailyEmailProfile

    profile = DailyEmailProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = DailyEmailProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()
    return profile


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@daily_email_bp.route("/")
@login_required
def index():
    log_project_visit("daily_email", "Daily Email")
    from app.projects.daily_email.models import DailyEmailSendLog

    profile = _get_or_create_profile()

    last_send = (
        DailyEmailSendLog.query
        .filter_by(user_id=current_user.id, status="sent")
        .order_by(DailyEmailSendLog.sent_at.desc())
        .first()
    )

    locations = list(
        current_user.daily_email_weather_locations
        .order_by(_weather_sort_col())
        .all()
    )

    return render_template(
        "daily_email/index.html",
        profile=profile,
        last_send=last_send,
        locations=locations,
        credits=current_user.credits or 0,
    )


# ---------------------------------------------------------------------------
# Settings — GET
# ---------------------------------------------------------------------------

@daily_email_bp.route("/settings")
@login_required
def settings():
    profile = _get_or_create_profile()
    locations = list(
        current_user.daily_email_weather_locations
        .order_by(_weather_sort_col())
        .all()
    )
    return render_template(
        "daily_email/settings.html",
        profile=profile,
        locations=locations,
        max_weather=MAX_WEATHER_LOCATIONS,
        hours=list(range(24)),
    )


# ---------------------------------------------------------------------------
# Settings — save master profile
# ---------------------------------------------------------------------------

@daily_email_bp.route("/settings/save", methods=["POST"])
@login_required
def settings_save():
    profile = _get_or_create_profile()

    profile.digest_enabled = request.form.get("digest_enabled") == "on"
    try:
        hour = int(request.form.get("send_hour_local", 6))
        profile.send_hour_local = max(0, min(23, hour))
    except (TypeError, ValueError):
        profile.send_hour_local = 6

    profile.include_weather = request.form.get("include_weather") == "on"
    profile.include_stocks = request.form.get("include_stocks") == "on"
    profile.include_sports = request.form.get("include_sports") == "on"
    profile.include_jobs = request.form.get("include_jobs") == "on"
    profile.updated_at = datetime.utcnow()

    db.session.commit()
    flash("Settings saved.", "success")
    return redirect(url_for("daily_email.settings"))


# ---------------------------------------------------------------------------
# Weather locations
# ---------------------------------------------------------------------------

@daily_email_bp.route("/settings/weather/add", methods=["POST"])
@login_required
def weather_add():
    from app.projects.daily_email.models import DailyEmailWeatherLocation
    from app.projects.daily_email.modules.weather import geocode_location

    query = request.form.get("location_query", "").strip()
    if not query:
        flash("Please enter a city name or ZIP code.", "error")
        return redirect(url_for("daily_email.settings"))

    existing_count = current_user.daily_email_weather_locations.count()
    if existing_count >= MAX_WEATHER_LOCATIONS:
        flash(f"You can save up to {MAX_WEATHER_LOCATIONS} weather locations.", "error")
        return redirect(url_for("daily_email.settings"))

    result = geocode_location(query)
    if not result:
        flash(f"Location not found for \u201c{query}\u201d. Try a city name or ZIP code.", "error")
        return redirect(url_for("daily_email.settings"))

    loc = DailyEmailWeatherLocation(
        user_id=current_user.id,
        display_label=result["label"],
        lat=result["lat"],
        lon=result["lon"],
        sort_order=existing_count,
    )
    db.session.add(loc)
    db.session.commit()
    flash(f"Added \u201c{result['label']}\u201d.", "success")
    return redirect(url_for("daily_email.settings"))


@daily_email_bp.route("/settings/weather/delete/<int:loc_id>", methods=["POST"])
@login_required
def weather_delete(loc_id):
    from app.projects.daily_email.models import DailyEmailWeatherLocation

    loc = DailyEmailWeatherLocation.query.filter_by(
        id=loc_id, user_id=current_user.id
    ).first_or_404()
    db.session.delete(loc)
    db.session.commit()
    flash("Location removed.", "success")
    return redirect(url_for("daily_email.settings"))


# ---------------------------------------------------------------------------
# In-browser preview (no send, no credit)
# ---------------------------------------------------------------------------

@daily_email_bp.route("/preview", methods=["POST"])
@login_required
def preview():
    from app.projects.daily_email.email_builder import build_digest_html
    from app.projects.daily_email.modules.weather import render_weather_section

    profile = _get_or_create_profile()
    locations = list(
        current_user.daily_email_weather_locations
        .order_by(_weather_sort_col())
        .all()
    )

    module_results = {
        "weather": render_weather_section(locations, user_timezone=current_user.time_zone or "UTC") if profile.include_weather and locations else None,
        "stocks": None,
        "sports": None,
        "jobs": None,
    }

    html = build_digest_html(current_user, profile, module_results)
    return Response(html, mimetype="text/html")


# ---------------------------------------------------------------------------
# Admin: send now
# ---------------------------------------------------------------------------

@daily_email_bp.route("/send-now", methods=["POST"])
@login_required
@admin_required
def send_now():
    from app.projects.daily_email.commands import _build_and_send

    profile = _get_or_create_profile()

    if (current_user.credits or 0) < 1:
        flash("Not enough credits to send.", "error")
        return redirect(url_for("daily_email.index"))

    ok = _build_and_send(current_user, profile, local_date=None, is_test=True)
    if ok:
        flash("Digest sent successfully.", "success")
    else:
        flash("Send failed — check the logs.", "error")
    return redirect(url_for("daily_email.index"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _weather_sort_col():
    from app.projects.daily_email.models import DailyEmailWeatherLocation
    return DailyEmailWeatherLocation.sort_order
