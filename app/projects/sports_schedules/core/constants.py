"""
Constants for Sports Schedules: dimensions, filter options, display labels.
Single source of truth for query builder validation and UI multiselects.
"""
from app.projects.sports_schedule_admin.core.espn_client import (
    ESPNClient,
)

# --- Low-cardinality filter options (schema values) ---
SPORTS = ["basketball", "hockey", "football", "baseball", "soccer"]

LEVELS = ["pro", "college"]

DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

# US state codes (DC included for sports venues)
US_STATE_CODES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
]

# League: build from ESPN config, sorted for consistent UI order
LEAGUE_CODES = sorted(ESPNClient.LEAGUE_MAP.keys())
LEAGUE_DISPLAY_NAMES = ESPNClient.LEAGUE_DISPLAY_NAMES

def _league_options():
    """List of (value, label) for league multiselect."""
    return [
        (code, LEAGUE_DISPLAY_NAMES.get(code, code))
        for code in LEAGUE_CODES
    ]


# --- LOW_CARDINALITY_OPTIONS: column -> [(value, label), ...] ---
LOW_CARDINALITY_OPTIONS = {
    "sport": [(v, v.title()) for v in SPORTS],
    "league": _league_options(),
    "level": [(v, v.title()) for v in LEVELS],
    "day": [(v, v) for v in DAYS],
    "home_state": [(code, code) for code in US_STATE_CODES],
}


# --- Field order for sidebar and filter bar (consistent UI order) ---
FIELD_ORDER = [
    "day", "date", "time", "road_team", "home_team", "either_team",
    "home_city", "home_state", "location", "league", "sport", "level",
]

# Fields that can only be used as filters (no dimension)
FILTER_ONLY_FIELDS = ["either_team"]

# Default dimensions when page loads with no URL state
DEFAULT_DIMENSIONS = ["date", "time", "home_team", "road_team"]

# Default filters when page loads with no URL state (field -> value dict for date, or field name for simple)
DEFAULT_FILTERS = {"date": "next_week"}

# --- DIMENSION_LABELS: column -> display label (from PRD) ---
DIMENSION_LABELS = {
    "either_team": "Either Team",
    "sport": "Sport",
    "level": "Level",
    "league": "League",
    "date": "Date",
    "day": "Day",
    "time": "Time (ET)",
    "home_team": "Home Team",
    "road_team": "Road Team",
    "location": "Location",
    "home_city": "City",
    "home_state": "State",
}
