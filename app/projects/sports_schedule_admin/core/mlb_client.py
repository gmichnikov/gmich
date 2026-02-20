"""
Client for fetching Minor League Baseball schedules from the MLB Stats API.

See MILB_SYNC_NOTES.md for known issues (API truncation on large ranges, date handling)
and why MAX_DAYS_PER_REQUEST is kept small.
"""
import json
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import pytz
import requests

from app.projects.sports_schedule_admin.core.leagues import MILB_LEAGUE_MAP

logger = logging.getLogger(__name__)

MLB_BASE = "https://statsapi.mlb.com/api/v1"
ET_TZ = pytz.timezone("America/New_York")
# Use 7-day chunks - matches the small syncs that work; larger ranges return incomplete data
MAX_DAYS_PER_REQUEST = 7

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
            # Fetch in chunks (smaller = more reliable; large ranges can return incomplete data)
            all_games = []
            current = start_date
            while current <= end_date:
                chunk_end = min(current + timedelta(days=MAX_DAYS_PER_REQUEST - 1), end_date)
                games = self._fetch_range(sport_id, league_code, current, chunk_end)
                logger.info(f"{league_code} chunk {current} to {chunk_end}: {len(games)} games")
                all_games.extend(games)
                current = chunk_end + timedelta(days=1)
            logger.info(f"{league_code} total from all chunks: {len(all_games)} games")
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
        logger.info(f"MLB API request {league_code}: {params['startDate']} to {params['endDate']}")

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
            block_date = date_block.get("date", "?")
            block_games = date_block.get("games", [])
            parsed_count = 0
            for game in block_games:
                try:
                    record = self._parse_game(game, league_code, block_date)
                    if record:
                        games.append(record)
                        parsed_count += 1
                except (KeyError, IndexError, ValueError) as e:
                    logger.error(f"Error parsing game {game.get('gamePk')} (date {block_date}): {e}")
                    continue
            if block_games and league_code == "AA":
                logger.info(f"AA block {block_date}: API had {len(block_games)}, parsed {parsed_count}")

        if league_code == "AA" and games:
            by_date = Counter(r["date"] for r in games)
            logger.info(f"AA total parsed: {len(games)} games across {len(by_date)} dates; sample: {dict(by_date.most_common(5))}")

        return games

    def _parse_game(self, game: dict, league_code: str, official_date: str | None = None) -> dict | None:
        """Parse a single game into DoltHub record.

        Uses official_date (from API date block) when provided to avoid timezone-derived
        mismatches. Falls back to gameDate converted to ET for backwards compatibility.
        """
        home = game["teams"]["home"]["team"]
        away = game["teams"]["away"]["team"]
        home_team = home["name"]
        road_team = away["name"]

        # Date: use officialDate (block date from API) to match API organization and avoid
        # timezone edge cases where gameDate crosses midnight.
        dt_str = game.get("gameDate")
        if not dt_str:
            return None

        if official_date:
            game_date = official_date
        else:
            game_date = game.get("officialDate")
        if not game_date:
            utc_dt = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.UTC)
            et_dt = utc_dt.astimezone(ET_TZ)
            game_date = et_dt.strftime("%Y-%m-%d")

        utc_dt = datetime.strptime(dt_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=pytz.UTC)
        et_dt = utc_dt.astimezone(ET_TZ)
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
