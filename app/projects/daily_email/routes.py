from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, jsonify
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
MAX_SPORTS_WATCHES = 10


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
    stock_tickers = list(current_user.daily_email_stock_tickers.limit(1).all())
    sports_watches = list(current_user.daily_email_sports_watches.limit(1).all())

    return render_template(
        "daily_email/index.html",
        profile=profile,
        last_send=last_send,
        locations=locations,
        stock_tickers=stock_tickers,
        sports_watches=sports_watches,
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
    stock_tickers = list(
        current_user.daily_email_stock_tickers
        .order_by(_stock_sort_col())
        .all()
    )
    sports_watches = list(
        current_user.daily_email_sports_watches
        .order_by(_sports_sort_col())
        .all()
    )
    return render_template(
        "daily_email/settings.html",
        profile=profile,
        locations=locations,
        max_weather=MAX_WEATHER_LOCATIONS,
        stock_tickers=stock_tickers,
        max_stocks=MAX_STOCK_TICKERS,
        sports_watches=sports_watches,
        max_sports=MAX_SPORTS_WATCHES,
        hours=list(range(24)),
        stocks_error=request.args.get("stocks_error"),
        stocks_added=request.args.get("stocks_added"),
        sports_error=request.args.get("sports_error"),
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
    # include_jobs is "coming soon" in UI: submitted via hidden field only
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

    from app.projects.daily_email.modules.stocks import render_stocks_section
    from app.projects.daily_email.modules.sports import render_sports_section
    stock_tickers = list(
        current_user.daily_email_stock_tickers
        .order_by(_stock_sort_col())
        .all()
    )
    sports_watches = list(
        current_user.daily_email_sports_watches
        .order_by(_sports_sort_col())
        .all()
    )
    tz = current_user.time_zone or "UTC"
    module_results = {
        "weather": render_weather_section(locations, user_timezone=tz) if profile.include_weather and locations else None,
        "stocks": render_stocks_section(stock_tickers) if profile.include_stocks and stock_tickers else None,
        "sports": render_sports_section(sports_watches, user_timezone=tz) if profile.include_sports else None,
        "jobs": None,
    }

    html = build_digest_html(current_user, profile, module_results)
    return Response(html, mimetype="text/html")


# ---------------------------------------------------------------------------
# Sports watches
# ---------------------------------------------------------------------------


@daily_email_bp.route("/settings/sports/teams")
@login_required
def sports_teams():
    from app.projects.daily_email.modules.sports import SUPPORTED_LEAGUE_CODES
    from app.projects.sports_schedule_admin.core.espn_client import ESPNClient

    league = (request.args.get("league") or "").upper().strip()
    if league not in SUPPORTED_LEAGUE_CODES:
        return jsonify({"error": "Invalid league", "teams": []}), 400
    client = ESPNClient()
    raw = client.fetch_teams(league)
    teams = [
        {
            "id": str(t["espn_team_id"]),
            "name": t.get("name") or "",
            "abbr": t.get("abbreviation") or "",
        }
        for t in raw
        if t.get("espn_team_id") is not None
    ]
    teams.sort(key=lambda x: (x.get("name") or "").lower())
    return jsonify({"teams": teams})


@daily_email_bp.route("/settings/sports/add", methods=["POST"])
@login_required
def sports_add():
    from app.projects.daily_email.models import DailyEmailSportsWatch
    from app.projects.daily_email.modules.sports import SUPPORTED_LEAGUE_CODES

    league_code = (request.form.get("league_code") or "").upper().strip()
    team_id = (request.form.get("espn_team_id") or "").strip()
    display_name = (request.form.get("team_display_name") or "").strip()

    if league_code not in SUPPORTED_LEAGUE_CODES or not team_id or not display_name:
        return redirect(
            url_for("daily_email.settings", sports_error="League, team, and name are all required.")
        )

    n = current_user.daily_email_sports_watches.count()
    if n >= MAX_SPORTS_WATCHES:
        return redirect(
            url_for("daily_email.settings", sports_error=f"Maximum {MAX_SPORTS_WATCHES} team watches allowed.")
        )

    dup = (
        current_user.daily_email_sports_watches
        .filter_by(league_code=league_code, espn_team_id=team_id)
        .first()
    )
    if dup:
        return redirect(
            url_for("daily_email.settings", sports_error=f"That team is already on your list.")
        )

    row = DailyEmailSportsWatch(
        user_id=current_user.id,
        league_code=league_code,
        espn_team_id=team_id,
        team_display_name=display_name,
        sort_order=n,
    )
    db.session.add(row)
    db.session.commit()
    return redirect(url_for("daily_email.settings", sports_added="sports"))


@daily_email_bp.route("/settings/sports/delete/<int:watch_id>", methods=["POST"])
@login_required
def sports_delete(watch_id):
    from app.projects.daily_email.models import DailyEmailSportsWatch

    w = DailyEmailSportsWatch.query.filter_by(
        id=watch_id, user_id=current_user.id
    ).first_or_404()
    db.session.delete(w)
    db.session.commit()
    return redirect(url_for("daily_email.settings"))


# ---------------------------------------------------------------------------
# Stock tickers
# ---------------------------------------------------------------------------

MAX_STOCK_TICKERS = 10


@daily_email_bp.route("/settings/stocks/add", methods=["POST"])
@login_required
def stocks_add():
    from app.projects.daily_email.models import DailyEmailStockTicker
    from app.projects.daily_email.modules.stocks import validate_ticker

    symbol = request.form.get("symbol", "").strip().upper()
    if not symbol:
        return redirect(url_for("daily_email.settings", stocks_error="Please enter a ticker symbol."))

    existing_count = current_user.daily_email_stock_tickers.count()
    if existing_count >= MAX_STOCK_TICKERS:
        return redirect(url_for("daily_email.settings", stocks_error=f"You can save up to {MAX_STOCK_TICKERS} tickers."))

    already = current_user.daily_email_stock_tickers.filter_by(symbol=symbol).first()
    if already:
        return redirect(url_for("daily_email.settings", stocks_error=f"{symbol} is already in your list."))

    if not validate_ticker(symbol):
        return redirect(url_for("daily_email.settings", stocks_error=f"\u201c{symbol}\u201d doesn\u2019t appear to be a valid ticker."))

    ticker = DailyEmailStockTicker(
        user_id=current_user.id,
        symbol=symbol,
        sort_order=existing_count,
    )
    db.session.add(ticker)
    db.session.commit()
    return redirect(url_for("daily_email.settings", stocks_added=symbol))


@daily_email_bp.route("/settings/stocks/delete/<int:ticker_id>", methods=["POST"])
@login_required
def stocks_delete(ticker_id):
    from app.projects.daily_email.models import DailyEmailStockTicker

    ticker = DailyEmailStockTicker.query.filter_by(
        id=ticker_id, user_id=current_user.id
    ).first_or_404()
    db.session.delete(ticker)
    db.session.commit()
    flash(f"Removed {ticker.symbol}.", "success")
    return redirect(url_for("daily_email.settings"))


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


def _stock_sort_col():
    from app.projects.daily_email.models import DailyEmailStockTicker
    return DailyEmailStockTicker.sort_order


def _sports_sort_col():
    from app.projects.daily_email.models import DailyEmailSportsWatch
    return DailyEmailSportsWatch.sort_order
