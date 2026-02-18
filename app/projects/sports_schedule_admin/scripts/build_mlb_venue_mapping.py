#!/usr/bin/env python3
"""
Build venue_id -> {city, state} mapping for MLB minor league ballparks.

Run from project root:
  python -m app.projects.sports_schedule_admin.scripts.build_mlb_venue_mapping [--from-saved]

Modes:
  - Default: Fetch from MLB Stats API, save raw responses to data/mlb_raw/, generate mapping.
  - --from-saved: Read saved responses from data/mlb_raw/, regenerate mapping only (no API calls).

If you prefer to save API responses manually, fetch these URLs and save to data/mlb_raw/:
  - https://statsapi.mlb.com/api/v1/teams?season=2025&sportId=11  -> teams_sport_11.json
  - https://statsapi.mlb.com/api/v1/teams?season=2025&sportId=12  -> teams_sport_12.json
  - https://statsapi.mlb.com/api/v1/teams?season=2025&sportId=13  -> teams_sport_13.json
  - https://statsapi.mlb.com/api/v1/teams?season=2025&sportId=14  -> teams_sport_14.json
  - For each venue ID in those files: https://statsapi.mlb.com/api/v1/venues/{id}?hydrate=location
    -> venues/{id}.json (e.g. venues/2541.json)

Then run with --from-saved to generate the mapping.
"""
import argparse
import json
from pathlib import Path

import requests

# Paths relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
RAW_DIR = DATA_DIR / "mlb_raw"
VENUES_DIR = RAW_DIR / "venues"
MAPPING_FILE = DATA_DIR / "mlb_venue_city_state.json"

MLB_BASE = "https://statsapi.mlb.com/api/v1"
SPORT_IDS = (11, 12, 13, 14)  # AAA, AA, High-A, Single-A


def ensure_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    VENUES_DIR.mkdir(parents=True, exist_ok=True)


def fetch_teams(sport_id: int) -> dict:
    """Fetch teams for a minor league sport level."""
    url = f"{MLB_BASE}/teams"
    resp = requests.get(url, params={"season": 2025, "sportId": sport_id}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch_venue(venue_id: int) -> dict:
    """Fetch venue details with location (city, state)."""
    url = f"{MLB_BASE}/venues/{venue_id}"
    resp = requests.get(url, params={"hydrate": "location"}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def collect_venue_ids_from_teams(teams_data: list[dict]) -> set[int]:
    """Extract unique venue IDs from teams responses."""
    ids = set()
    for data in teams_data:
        for team in data.get("teams", []):
            venue = team.get("venue")
            if venue and venue.get("id"):
                ids.add(venue["id"])
    return ids


# Minimal full-name -> 2-letter for venues that only return full state name
_STATE_NAME_TO_CODE = {
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
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}


def parse_venue_location(venue_data: dict) -> tuple[str, str] | None:
    """Extract (city, state_abbrev) from venue response. Returns None if missing."""
    venues = venue_data.get("venues", [])
    if not venues:
        return None
    loc = venues[0].get("location")
    if not loc:
        return None
    city = loc.get("city", "").strip()
    state = loc.get("stateAbbrev", "").strip() or loc.get("state", "").strip()
    if not city:
        return None
    # Normalize full state name to 2-letter if needed
    if state and len(state) > 2:
        state = _STATE_NAME_TO_CODE.get(state.lower(), state)
    return (city, state[:2].upper() if len(state) >= 2 else state)


def load_saved_teams() -> list[dict]:
    """Load teams data from saved files."""
    result = []
    for sid in SPORT_IDS:
        path = RAW_DIR / f"teams_sport_{sid}.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}. Run without --from-saved to fetch, or save the API response manually.")
        with open(path) as f:
            result.append(json.load(f))
    return result


def load_saved_venue(venue_id: int) -> dict | None:
    """Load a single venue from saved file."""
    path = VENUES_DIR / f"{venue_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def run_fetch_mode():
    """Fetch from API, save raw responses, build mapping."""
    ensure_dirs()
    teams_data = []

    print("Fetching teams for sportIds 11,12,13,14...")
    for sid in SPORT_IDS:
        data = fetch_teams(sid)
        path = RAW_DIR / f"teams_sport_{sid}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        teams_data.append(data)
        print(f"  Saved {path} ({len(data.get('teams', []))} teams)")

    venue_ids = collect_venue_ids_from_teams(teams_data)
    print(f"\nFound {len(venue_ids)} unique venue IDs. Fetching venue details...")

    mapping = {}
    for i, vid in enumerate(sorted(venue_ids), 1):
        path = VENUES_DIR / f"{vid}.json"
        try:
            data = fetch_venue(vid)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"  Warning: venue {vid}: {e}")
            continue
        loc = parse_venue_location(data)
        if loc:
            mapping[str(vid)] = {"city": loc[0], "state": loc[1]}
        else:
            print(f"  Warning: venue {vid} has no location data")
        if i % 10 == 0:
            print(f"  Fetched {i}/{len(venue_ids)} venues...")

    _write_mapping(mapping)
    print(f"\nWrote {MAPPING_FILE} ({len(mapping)} venues). Review before use.")


def run_from_saved_mode():
    """Read saved responses, build mapping (no API calls)."""
    teams_data = load_saved_teams()
    venue_ids = collect_venue_ids_from_teams(teams_data)

    mapping = {}
    missing = []
    for vid in venue_ids:
        data = load_saved_venue(vid)
        if not data:
            missing.append(vid)
            continue
        loc = parse_venue_location(data)
        if loc:
            mapping[str(vid)] = {"city": loc[0], "state": loc[1]}
        else:
            print(f"  Warning: venue {vid} has no location data in saved file")

    if missing:
        print(f"  Missing venue files for IDs: {missing[:10]}{'...' if len(missing) > 10 else ''}")
        print(f"  Run without --from-saved to fetch them, or save venues/{id}.json manually.")

    _write_mapping(mapping)
    print(f"\nWrote {MAPPING_FILE} ({len(mapping)} venues). Review before use.")


def _write_mapping(mapping: dict):
    """Write mapping to JSON file (sorted by venue ID for easy diffing)."""
    sorted_mapping = dict(sorted(mapping.items(), key=lambda x: int(x[0])))
    with open(MAPPING_FILE, "w") as f:
        json.dump(sorted_mapping, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Build MLB minor league venue -> city/state mapping")
    parser.add_argument("--from-saved", action="store_true", help="Read from saved API responses only (no network)")
    args = parser.parse_args()

    if args.from_saved:
        run_from_saved_mode()
    else:
        run_fetch_mode()


if __name__ == "__main__":
    main()
