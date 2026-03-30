import logging
from datetime import datetime, timezone

import pytz

logger = logging.getLogger(__name__)

# v1 supported sports (uppercase league code → sport_key used in DB)
SUPPORTED_LEAGUES = ["NFL", "NBA", "MLB", "NHL"]

# Maps uppercase league code → lowercase sport_key stored in DB / used in URLs
LEAGUE_TO_SPORT_KEY = {
    "NFL": "nfl",
    "NBA": "nba",
    "MLB": "mlb",
    "NHL": "nhl",
}

SPORT_KEY_TO_LEAGUE = {v: k for k, v in LEAGUE_TO_SPORT_KEY.items()}

SPORT_DISPLAY = {
    "nfl": "NFL",
    "nba": "NBA",
    "mlb": "MLB",
    "nhl": "NHL",
}

SUPPORTED_SPORTS = list(SPORT_DISPLAY.keys())

ET_TZ = pytz.timezone("America/New_York")


def _parse_utc_dt(date_str):
    """Parse ESPN ISO 8601 UTC string (e.g. '2026-03-30T00:00Z') into a UTC datetime."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _score_int(value):
    """Convert a score string/value to int, or None if missing/invalid."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_scoreboard(sport_key, api_response):
    """
    Parse an ESPN scoreboard API response into a list of normalized game dicts.

    Each dict matches the ScoresGame column layout:
        espn_event_id, sport_key, game_date, start_time_utc,
        home_team, away_team, home_score, away_score,
        status_state, status_detail

    Malformed events are skipped with a warning; the rest are returned.
    """
    events = api_response.get("events", [])
    games = []

    for event in events:
        try:
            event_id = str(event["id"])
            competition = event["competitions"][0]

            home_team = ""
            away_team = ""
            home_score = None
            away_score = None

            for competitor in competition.get("competitors", []):
                name = competitor.get("team", {}).get("displayName", "")
                score = _score_int(competitor.get("score"))
                if competitor.get("homeAway") == "home":
                    home_team = name
                    home_score = score
                else:
                    away_team = name
                    away_score = score

            # Date / time
            start_time_utc = _parse_utc_dt(event.get("date", ""))
            if start_time_utc:
                game_date = start_time_utc.astimezone(ET_TZ).date()
            else:
                # Fall back to raw date string prefix
                raw_date = event.get("date", "")[:10]
                try:
                    from datetime import date
                    game_date = date.fromisoformat(raw_date)
                except ValueError:
                    logger.warning(
                        "sports_scores: skipping event %s — unparseable date %r",
                        event_id,
                        event.get("date"),
                    )
                    continue

            # Status
            status = event.get("status", {})
            status_type = status.get("type", {})
            status_state = status_type.get("state", "pre")  # "pre", "in", "post"
            status_detail = status_type.get("shortDetail", "")

            games.append(
                {
                    "espn_event_id": event_id,
                    "sport_key": sport_key,
                    "game_date": game_date,
                    "start_time_utc": start_time_utc,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_score": home_score,
                    "away_score": away_score,
                    "status_state": status_state,
                    "status_detail": status_detail,
                }
            )

        except (KeyError, IndexError, TypeError) as exc:
            logger.warning(
                "sports_scores: skipping event %s during parse — %s",
                event.get("id", "?"),
                exc,
            )
            continue

    return games
