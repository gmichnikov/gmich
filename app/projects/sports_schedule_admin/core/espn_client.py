import requests
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class ESPNClient:
    """
    Client for fetching sports data from ESPN's unofficial API.
    """
    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"

    LEAGUE_MAP = {
        "MLB": ("baseball", "mlb", "pro"),
        "NBA": ("basketball", "nba", "pro"),
        "NFL": ("football", "nfl", "pro"),
        "NHL": ("hockey", "nhl", "pro"),
        "MLS": ("soccer", "usa.1", "pro"),
        "EPL": ("soccer", "eng.1", "pro"),
    }

    def fetch_schedule(self, league_code, date_str):
        """
        Fetch schedule for a specific league and date (YYYYMMDD).
        """
        if league_code not in self.LEAGUE_MAP:
            logger.error(f"Unsupported league: {league_code}")
            return []

        sport, league, level = self.LEAGUE_MAP[league_code]
        url = f"{self.BASE_URL}/{sport}/{league}/scoreboard"
        params = {"dates": date_str}

        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            return self._parse_events(data, league_code, level, sport)
        except requests.exceptions.RequestException as e:
            logger.error(f"ESPN API error for {league_code} on {date_str}: {e}")
            return []

    def _parse_events(self, data, league_code, level, sport_name):
        """
        Parse ESPN events into the DoltHub schema format.
        """
        events = data.get("events", [])
        parsed_games = []

        for event in events:
            try:
                competition = event["competitions"][0]
                
                # Teams
                home_team = ""
                road_team = ""
                for competitor in competition["competitors"]:
                    if competitor["homeAway"] == "home":
                        home_team = competitor["team"]["displayName"]
                    else:
                        road_team = competitor["team"]["displayName"]

                # Date and Time
                # ESPN returns ISO 8601 UTC: 2026-02-12T03:00Z
                dt_str = event["date"]
                dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%MZ")
                
                game_date = dt.strftime("%Y-%m-%d")
                game_day = dt.strftime("%A")
                # Format time as "7:30 PM" or similar
                game_time = dt.strftime("%I:%M %p")

                # Venue / Location
                venue = competition.get("venue", {})
                location = venue.get("fullName", "")
                address = venue.get("address", {})
                home_city = address.get("city", "")
                home_state = address.get("state", "")

                # Primary Key Generation: {league}_{date}_{home_slug}_vs_{road_slug}
                home_slug = self._slugify(home_team)
                road_slug = self._slugify(road_team)
                primary_key = f"{league_code.lower()}_{game_date}_{home_slug}_vs_{road_slug}"

                game_record = {
                    "primary_key": primary_key,
                    "sport": sport_name,
                    "level": level,
                    "league": league_code,
                    "date": game_date,
                    "day": game_day,
                    "time": game_time,
                    "home_team": home_team,
                    "road_team": road_team,
                    "location": location,
                    "home_city": home_city,
                    "home_state": home_state
                }
                parsed_games.append(game_record)

            except (KeyError, IndexError, ValueError) as e:
                logger.error(f"Error parsing event {event.get('id')}: {e}")
                continue

        return parsed_games

    def _slugify(self, text):
        """
        Simple slugifier for team names.
        """
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s-]", "", text)
        text = re.sub(r"[\s-]+", "_", text).strip("_")
        return text
