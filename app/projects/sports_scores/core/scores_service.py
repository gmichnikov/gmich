import logging
import requests
from datetime import datetime, timezone, timedelta, date

import pytz

from app import db
from app.projects.sports_scores.models import ScoresFetchLog, ScoresGame
from app.projects.sports_scores.core.espn_parser import (
    parse_scoreboard,
    SPORT_KEY_TO_LEAGUE,
    ET_TZ,
)
from app.projects.sports_schedule_admin.core.espn_client import ESPNClient

logger = logging.getLogger(__name__)

FETCH_THROTTLE_SECONDS = 60
ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"


def _utc_now():
    return datetime.now(timezone.utc)


def _today_et():
    """Return today's date in US Eastern time."""
    return datetime.now(ET_TZ).date()


# ---------------------------------------------------------------------------
# Throttle helpers
# ---------------------------------------------------------------------------

def get_fetch_log(sport_key):
    """Return the ScoresFetchLog row for this sport, or None if it doesn't exist."""
    return ScoresFetchLog.query.filter_by(sport_key=sport_key).first()


def should_fetch(sport_key):
    """
    Return True if we should make a fresh ESPN call for this sport.
    True when: no fetch log exists, or last fetch was > FETCH_THROTTLE_SECONDS ago.
    """
    log = get_fetch_log(sport_key)
    if log is None:
        return True
    last = log.last_fetched_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    elapsed = (_utc_now() - last).total_seconds()
    return elapsed > FETCH_THROTTLE_SECONDS


# ---------------------------------------------------------------------------
# Fetch + store
# ---------------------------------------------------------------------------

def _scoreboard_url(sport_key):
    """Build the ESPN scoreboard URL for a given sport_key."""
    league_code = SPORT_KEY_TO_LEAGUE.get(sport_key.upper(), sport_key.upper())
    client = ESPNClient()
    if league_code not in client.LEAGUE_MAP:
        raise ValueError(f"Unsupported league code: {league_code}")
    sport, league, _ = client.LEAGUE_MAP[league_code]
    return f"{ESPN_BASE_URL}/{sport}/{league}/scoreboard"


def _upsert_games(games):
    """Upsert a list of parsed game dicts into the DB."""
    for g in games:
        existing = ScoresGame.query.filter_by(
            espn_event_id=g["espn_event_id"],
            sport_key=g["sport_key"],
        ).first()

        if existing:
            existing.game_date = g["game_date"]
            existing.start_time_utc = g["start_time_utc"]
            existing.home_team = g["home_team"]
            existing.away_team = g["away_team"]
            existing.home_score = g["home_score"]
            existing.away_score = g["away_score"]
            existing.status_state = g["status_state"]
            existing.status_detail = g["status_detail"]
            existing.updated_at = _utc_now()
        else:
            db.session.add(ScoresGame(
                espn_event_id=g["espn_event_id"],
                sport_key=g["sport_key"],
                game_date=g["game_date"],
                start_time_utc=g["start_time_utc"],
                home_team=g["home_team"],
                away_team=g["away_team"],
                home_score=g["home_score"],
                away_score=g["away_score"],
                status_state=g["status_state"],
                status_detail=g["status_detail"],
                updated_at=_utc_now(),
            ))


def fetch_and_store(sport_key, anchor_date=None):
    """
    Fetch the ESPN scoreboard for sport_key covering the full display window
    (anchor_date - 2 days through anchor_date) in a single API call using a
    date range (dates=YYYYMMDD-YYYYMMDD), then upsert all games into the DB.

    anchor_date defaults to today in ET.
    Updates the fetch log on success.
    Returns True on success, False on ESPN error.
    """
    if anchor_date is None:
        anchor_date = _today_et()

    start_date = anchor_date - timedelta(days=2)
    dates_param = f"{start_date.strftime('%Y%m%d')}-{anchor_date.strftime('%Y%m%d')}"

    try:
        url = _scoreboard_url(sport_key)
    except ValueError as exc:
        logger.error("sports_scores fetch_and_store: %s", exc)
        return False

    try:
        response = requests.get(url, params={"dates": dates_param}, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        logger.error(
            "sports_scores: ESPN fetch failed for %s (dates=%s): %s",
            sport_key,
            dates_param,
            exc,
        )
        return False

    games = parse_scoreboard(sport_key, data)
    _upsert_games(games)

    log = get_fetch_log(sport_key)
    if log:
        log.last_fetched_at = _utc_now()
    else:
        db.session.add(ScoresFetchLog(sport_key=sport_key, last_fetched_at=_utc_now()))

    db.session.commit()
    logger.info(
        "sports_scores: stored %d games for %s (dates=%s)",
        len(games),
        sport_key,
        dates_param,
    )
    return True


# ---------------------------------------------------------------------------
# Query for display
# ---------------------------------------------------------------------------

def get_games_for_display(sport_key, anchor_date=None):
    """
    Return an ordered dict of {date_str: [game_dict, ...]} covering:
        anchor_date - 2 days, anchor_date - 1 day, anchor_date (today)

    anchor_date: a date object or None (defaults to today in ET).
    Dates with no games are included with an empty list so the template
    can show "No games scheduled."
    Games within each date are sorted by start_time_utc ascending.
    """
    if anchor_date is None:
        anchor_date = _today_et()

    dates = [anchor_date - timedelta(days=2), anchor_date - timedelta(days=1), anchor_date]

    rows = (
        ScoresGame.query
        .filter(
            ScoresGame.sport_key == sport_key,
            ScoresGame.game_date.in_(dates),
        )
        .order_by(ScoresGame.game_date.asc(), ScoresGame.start_time_utc.asc())
        .all()
    )

    # Build result dict — all three dates present even if empty
    result = {d.isoformat(): [] for d in dates}
    for row in rows:
        key = row.game_date.isoformat()
        result[key].append(_game_to_dict(row))

    return result


def get_games_for_team(team_name, limit=20):
    """
    Return up to `limit` most recent games (across all sports) where
    home_team or away_team matches team_name (exact, case-insensitive).
    Returns a flat list of game dicts ordered by game_date desc, start_time_utc desc.
    """
    from sqlalchemy import func, or_
    rows = (
        ScoresGame.query
        .filter(
            or_(
                func.lower(ScoresGame.home_team) == team_name.lower(),
                func.lower(ScoresGame.away_team) == team_name.lower(),
            )
        )
        .order_by(ScoresGame.game_date.desc(), ScoresGame.start_time_utc.desc())
        .limit(limit)
        .all()
    )
    return [_game_to_dict(row) for row in rows]


def _game_to_dict(game):
    """Serialize a ScoresGame row to a plain dict for template / JSON use."""
    start_et = None
    if game.start_time_utc:
        utc = game.start_time_utc
        if utc.tzinfo is None:
            utc = utc.replace(tzinfo=timezone.utc)
        start_et = utc.astimezone(ET_TZ).strftime("%-I:%M %p ET")

    return {
        "id": game.id,
        "espn_event_id": game.espn_event_id,
        "sport_key": game.sport_key,
        "game_date": game.game_date.isoformat(),
        "start_time_et": start_et,
        "home_team": game.home_team,
        "away_team": game.away_team,
        "home_score": game.home_score,
        "away_score": game.away_score,
        "status_state": game.status_state,
        "status_detail": game.status_detail,
        "updated_at": game.updated_at.isoformat() if game.updated_at else None,
    }
