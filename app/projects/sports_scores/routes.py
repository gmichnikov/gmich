import logging
from datetime import date, datetime, timezone, timedelta

from flask import Blueprint, render_template, request, jsonify

from app.utils.logging import log_project_visit
from app.projects.sports_scores.core.espn_parser import SUPPORTED_SPORTS, SPORT_DISPLAY
from app.projects.sports_scores.core.scores_service import (
    should_fetch,
    fetch_and_store,
    get_games_for_display,
    get_fetch_log,
    _today_et,
)

logger = logging.getLogger(__name__)

sports_scores_bp = Blueprint(
    "sports_scores",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/sports-scores/static",
    url_prefix="/sports-scores",
)


def _parse_anchor_date(date_str):
    """
    Parse a YYYY-MM-DD date string from the request.
    Returns a date object, or today in ET if missing/invalid.
    """
    if date_str:
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            pass
    return _today_et()


def _last_fetched_display(sport_key):
    """Return a human-readable 'Updated X min ago' string, or None."""
    log = get_fetch_log(sport_key)
    if not log:
        return None
    last = log.last_fetched_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - last
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "Updated just now"
    if minutes == 1:
        return "Updated 1 min ago"
    return f"Updated {minutes} min ago"


def _format_date_label(d, anchor_date):
    """Return 'Today, Mar 30', 'Yesterday, Mar 29', or 'Sat, Mar 28'."""
    if d == anchor_date:
        return "Today, " + d.strftime("%b %-d")
    if d == anchor_date - timedelta(days=1):
        return "Yesterday, " + d.strftime("%b %-d")
    return d.strftime("%a, %b %-d")


@sports_scores_bp.route("/")
def index():
    log_project_visit("sports_scores", "Sports Scores")

    sport_key = request.args.get("sport", "nfl").lower()
    if sport_key not in SUPPORTED_SPORTS:
        sport_key = "nfl"

    # Compute anchor_date once for the entire request so fetch + display use the same date
    anchor_date = _parse_anchor_date(request.args.get("date"))

    # Fetch from ESPN if throttle allows
    if should_fetch(sport_key):
        fetch_and_store(sport_key, anchor_date)

    games_by_date = get_games_for_display(sport_key, anchor_date)
    last_updated = _last_fetched_display(sport_key)

    # Build date labels for the template
    date_labels = {
        d: _format_date_label(date.fromisoformat(d), anchor_date)
        for d in games_by_date
    }

    return render_template(
        "sports_scores/index.html",
        sport_key=sport_key,
        supported_sports=SUPPORTED_SPORTS,
        sport_display=SPORT_DISPLAY,
        games_by_date=games_by_date,
        date_labels=date_labels,
        anchor_date=anchor_date.isoformat(),
        last_updated=last_updated,
    )


@sports_scores_bp.route("/api/scores")
def api_scores():
    """JSON endpoint returning scores for a sport. Respects the same throttle."""
    sport_key = request.args.get("sport", "nfl").lower()
    if sport_key not in SUPPORTED_SPORTS:
        return jsonify({"error": f"Unsupported sport. Choose from: {', '.join(SUPPORTED_SPORTS)}"}), 400

    anchor_date = _parse_anchor_date(request.args.get("date"))

    if should_fetch(sport_key):
        fetch_and_store(sport_key, anchor_date)

    games_by_date = get_games_for_display(sport_key, anchor_date)
    last_updated = _last_fetched_display(sport_key)

    return jsonify({
        "sport": sport_key,
        "anchor_date": anchor_date.isoformat(),
        "last_updated": last_updated,
        "games_by_date": games_by_date,
    })
