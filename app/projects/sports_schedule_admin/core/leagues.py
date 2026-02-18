"""
Shared league configuration for ESPN + MiLB (Minor League Baseball).
Single source of truth for admin and sports_schedules projects.
"""
from app.projects.sports_schedule_admin.core.espn_client import (
    ESPNClient,
)

# MiLB: league_code -> sportId (MLB Stats API)
MILB_LEAGUE_MAP = {
    "AAA": 11,  # Triple-A
    "AA": 12,   # Double-A
    "A+": 13,   # High-A
    "A": 14,    # Single-A
}

MILB_LEAGUE_DISPLAY_NAMES = {
    "AAA": "Triple-A (AAA)",
    "AA": "Double-A (AA)",
    "A+": "High-A (A+)",
    "A": "Single-A (A)",
}

# All leagues (ESPN + MiLB) for validation
ALL_LEAGUE_CODES = sorted(ESPNClient.LEAGUE_MAP.keys()) + sorted(MILB_LEAGUE_MAP.keys())

# Merged display names
LEAGUE_DISPLAY_NAMES = {**ESPNClient.LEAGUE_DISPLAY_NAMES, **MILB_LEAGUE_DISPLAY_NAMES}

# Season type for "current season" coverage (calendar = Jan-Dec, school = Aug-July)
LEAGUE_SEASON_TYPE = {
    **ESPNClient.LEAGUE_SEASON_TYPE,
    "AAA": "calendar",
    "AA": "calendar",
    "A+": "calendar",
    "A": "calendar",
}


def is_milb_league(league_code: str) -> bool:
    """Return True if league uses MLB Stats API."""
    return league_code in MILB_LEAGUE_MAP
