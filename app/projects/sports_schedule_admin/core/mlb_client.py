"""
Client for fetching Minor League Baseball schedules from the MLB Stats API.
"""
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import pytz
import requests

from app.projects.sports_schedule_admin.core.leagues import MILB_LEAGUE_MAP

logger = logging.getLogger(__name__)

MLB_BASE = "https://statsapi.mlb.com/api/v1"
ET_TZ = pytz.timezone("America/New_York")
MAX_DAYS_PER_REQUEST = 90

# Path to venue mapping
VENUE_MAPPING_PATH = Path(__file__).resolve().parent.parent / "data" / "mlb_venue_city_state.json"


def _load_venue_mapping() -> dict:
    """Load venue_id -> {city, state} from JSON."""
    if not VENUE_MAPPING_PATH.exists():
        logger.warning(f"Venue mapping not found at {VENUE_MAPPING_PATH}")
        return {}
    with open(VENUE_MAPPING_PATH) as f:
        return json.load(f)


def _slugify(text: str) -> str:
    """Slugify team name for primary key. Handle slashes (e.g. Scranton/Wilkes-Barre)."""
    text = text.replace("/", " ")  # Scranton/Wilkes-Barre -> Scranton Wilkes-Barre
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text).strip("_")
    return text


class MLBClient:
    """Client for MLB Stats API (Minor League Baseball)."""

    def __init__(self):
        self._venue_mapping = _load_venue_mapping()

    def fetch_schedule(
        self,
        league_code: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> list[dict]:
        """
        Fetch MiLB schedule for a date range. Returns list of game records in DoltHub schema format.
        """
        if league_code not in MILB_LEAGUE_MAP:
            logger.error(f"Unsupported MiLB league: {league_code}")
            return []

        sport_id = MILB_LEAGUE_MAP[league_code]
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        # Cap range to avoid API limits
        from datetime import timedelta

        delta = (end_date - start_date).days + 1
        if delta > MAX_DAYS_PER_REQUEST:
            # Fetch in chunks
            all_games = []
            current = start_date
            while current <= end_date:
                chunk_end = min(current + timedelta(days=MAX_DAYS_PER_REQUEST - 1), end_date)
                games = self._fetch_range(sport_id, league_code, current, chunk_end)
                all_games.extend(games)
                current = chunk_end + timedelta(days=1)
            return all_games

        return self._fetch_range(sport_id, league_code, start_date, end_date)

    def _fetch_range(
        self,
        sport_id: int,
        league_code: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> list[dict]:
        """Fetch a single date range from the API."""
        url = f"{MLB_BASE}/schedule"
        params = {
            "sportId": sport_id,
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return self._parse_games(data, league_code)
        except requests.exceptions.RequestException as e:
            logger.error(f"MLB API error for {league_code}: {e}")
            return []

    def _parse_games(self, data: dict, league_code: str) -> list[dict]:
        """Parse MLB schedule response into DoltHub schema format."""
        games = []
        for date_block in data.get("dates", []):
            for game in date_block.get("games", []):
                try:
                    record = self._parse_game(game, league_code)
                    if record:
                        games.append(record)
                except (KeyError, IndexError, ValueError) as e:
                    logger.error(f"Error parsing game {game.get('gamePk')}: {e}")
                    continue

        return games

    def _parse_game(self, game: dict, league_code: str) -> dict | None:
        """Parse a single game into DoltHub record."""
        home = game["teams"]["home"]["team"]
        away = game["teams"]["away"]["team"]
        home_team = home["name"]
        road_team = away["name"]

        # Date/time - MLB returns UTC (e.g. 2025-04-15T15:05:00Z)
        dt_str = game.get("gameDate")
        if not dt_str:
            return None

        utc_dt = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.UTC)
        et_dt = utc_dt.astimezone(ET_TZ)

        game_date = et_dt.strftime("%Y-%m-%d")
        game_day = et_dt.strftime("%A")
        game_time = et_dt.strftime("%I:%M %p")

        # Venue
        venue = game.get("venue", {})
        venue_id = venue.get("id")
        location = venue.get("name", "")

        home_city = ""
        home_state = ""
        if venue_id and self._venue_mapping:
            loc = self._venue_mapping.get(str(venue_id), {})
            home_city = loc.get("city", "")
            home_state = loc.get("state", "")

        # Primary key
        home_slug = _slugify(home_team)
        road_slug = _slugify(road_team)
        primary_key = f"{league_code.lower()}_{game_date}_{home_slug}_vs_{road_slug}"

        return {
            "primary_key": primary_key,
            "sport": "baseball",
            "level": "minor",
            "league": league_code,
            "date": game_date,
            "day": game_day,
            "time": game_time,
            "home_team": home_team,
            "road_team": road_team,
            "location": location,
            "home_city": home_city,
            "home_state": home_state,
        }
