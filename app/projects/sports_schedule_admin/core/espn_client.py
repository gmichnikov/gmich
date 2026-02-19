import requests
import logging
import re
import pytz
from datetime import datetime

logger = logging.getLogger(__name__)

# US state full name -> 2-letter code (for normalizing ESPN venue addresses)
STATE_NAME_TO_CODE = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC", "washington, d.c.": "DC",
}
US_STATE_CODES = set(STATE_NAME_TO_CODE.values())

class ESPNClient:
    """
    Client for fetching sports data from ESPN's unofficial API.
    """
    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"

    # Eastern Timezone for normalization
    ET_TZ = pytz.timezone("America/New_York")

    LEAGUE_MAP = {
        "MLB": ("baseball", "mlb", "pro"),
        "NCB": ("baseball", "college-baseball", "college"),
        "NBA": ("basketball", "nba", "pro"),
        "NFL": ("football", "nfl", "pro"),
        "NHL": ("hockey", "nhl", "pro"),
        "MLS": ("soccer", "usa.1", "pro"),
        "NWSL": ("soccer", "usa.nwsl", "pro"),
        "NCSM": ("soccer", "usa.ncaa.m.1", "college"),
        "NCSW": ("soccer", "usa.ncaa.w.1", "college"),
        "EPL": ("soccer", "eng.1", "pro"),
        "CL": ("soccer", "uefa.champions", "pro"),
        "EL": ("soccer", "uefa.europa", "pro"),
        "FA": ("soccer", "eng.fa", "pro"),
        "LC": ("soccer", "eng.league_cup", "pro"),
        "WC": ("soccer", "fifa.world", "pro"),
        "NCAAM": ("basketball", "mens-college-basketball", "college"),
        "NCAAW": ("basketball", "womens-college-basketball", "college"),
        "CFB": ("football", "college-football", "college"),
        "WNBA": ("basketball", "wnba", "pro"),
        "NCHM": ("hockey", "mens-college-hockey", "college"),
        "NCHW": ("hockey", "womens-college-hockey", "college"),
    }

    # Season type for "current season" filtering in coverage.
    # "calendar" = Jan 1 - Dec 31; "school" = Aug 1 - following July 31
    LEAGUE_SEASON_TYPE = {
        "MLB": "calendar",
        "NCB": "school",
        "MLS": "calendar",
        "NWSL": "calendar",
        "NCSM": "school",
        "NCSW": "school",
        "NBA": "school",
        "NFL": "school",
        "NHL": "school",
        "WNBA": "school",
        "NCAAM": "school",
        "NCAAW": "school",
        "NCHM": "school",
        "NCHW": "school",
        "CFB": "school",
        "EPL": "school",
        "CL": "school",
        "EL": "school",
        "FA": "school",
        "LC": "school",
        "WC": "calendar",  # World Cup is a summer tournament
    }

    # Human-readable display names for dropdowns (soccer codes spelled out)
    LEAGUE_DISPLAY_NAMES = {
        "CL": "Champions League (CL)",
        "EL": "Europa League (EL)",
        "FA": "FA Cup (FA)",
        "LC": "League Cup (LC)",
        "WC": "World Cup (WC)",
        "EPL": "English Premier League (EPL)",
        "MLS": "Major League Soccer (MLS)",
        "NWSL": "National Women's Soccer League (NWSL)",
        "NCSM": "Men's College Soccer (NCSM)",
        "NCSW": "Women's College Soccer (NCSW)",
        "NCB": "College Baseball (NCB)",
        "NCHM": "Men's College Hockey (NCHM)",
        "NCHW": "Women's College Hockey (NCHW)",
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

    def fetch_teams(self, league_code):
        """
        Fetch all teams for a given league (e.g., NCAAM).
        Returns a list of team dictionaries: {espn_team_id, name, abbreviation, sport, league_code}
        """
        if league_code not in self.LEAGUE_MAP:
            logger.error(f"Unsupported league for team discovery: {league_code}")
            return []

        sport_name, league_path, level = self.LEAGUE_MAP[league_code]
        url = f"{self.BASE_URL}/{sport_name}/{league_path}/teams"
        params = {"limit": 1000} # Get all teams in one go

        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            teams_data = []
            sports = data.get("sports", [])
            for s in sports:
                leagues = s.get("leagues", [])
                for l in leagues:
                    teams = l.get("teams", [])
                    for t_entry in teams:
                        t = t_entry.get("team", {})
                        teams_data.append({
                            "espn_team_id": t.get("id"),
                            "name": t.get("displayName"),
                            "abbreviation": t.get("abbreviation"),
                            "sport": sport_name,
                            "league_code": league_code
                        })
            return teams_data
        except requests.exceptions.RequestException as e:
            logger.error(f"ESPN Teams API error for {league_code}: {e}")
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
                # Parse as UTC
                utc_dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=pytz.UTC)
                
                # Convert to Eastern Time
                et_dt = utc_dt.astimezone(self.ET_TZ)
                
                game_date = et_dt.strftime("%Y-%m-%d")
                game_day = et_dt.strftime("%A")
                # Format time as "7:30 PM" or similar
                game_time = et_dt.strftime("%I:%M %p")

                # Venue / Location
                venue = competition.get("venue", {})
                location = venue.get("fullName", "")
                address = venue.get("address", {})
                home_city = address.get("city", "")
                home_state = self._normalize_state(address.get("state", ""))

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

    def _normalize_state(self, state_val):
        """
        Normalize state to 2-letter US code. ESPN may return "California" or "CA".
        Returns 2-letter code for US states, or original value for international/unknown.
        """
        if not state_val or not isinstance(state_val, str):
            return state_val or ""
        s = state_val.strip()
        if len(s) == 2 and s.upper() in US_STATE_CODES:
            return s.upper()
        key = s.lower()
        if key in STATE_NAME_TO_CODE:
            return STATE_NAME_TO_CODE[key]
        return s

    def _slugify(self, text):
        """
        Simple slugifier for team names.
        """
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s-]", "", text)
        text = re.sub(r"[\s-]+", "_", text).strip("_")
        return text
