"""
Geocoding helpers for distance-based filtering.

- zip_to_coords: looks up a zip code in the ss_zip_codes table
- citystate_to_coords: geocodes a city/state via Nominatim, caching results in ss_geocode_cache
- nearby_states: returns a list of state_ids whose zip codes fall within a bounding box around a point
"""
import logging
import time

from geopy.distance import geodesic
from geopy.geocoders import Nominatim

from app import db
from app.projects.sports_schedules.models import (
    SportsScheduleGeocodeCache,
    SportsScheduleZipCode,
)

logger = logging.getLogger(__name__)

_geolocator = Nominatim(user_agent="gmich-sports-schedules")

# Normalize full US state names to 2-letter codes. Also handles DC and common variants.
_STATE_NAME_TO_CODE = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
    # Canadian provinces present in the data
    "alberta": "AB", "british columbia": "BC", "ontario": "ON", "quebec": "QC",
    "manitoba": "MB",
}

# 2-letter codes for US states only (used to skip international/Canadian rows)
_US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
}


# Known international/non-US cities that appear in the schedule with no state value.
# Keyed by the exact home_city string as it appears in the data.
_INTERNATIONAL_CITY_COORDS: dict[str, tuple[float, float]] = {
    "Abu Dhabi": (24.4539, 54.3773),
    "Athens": (37.9838, 23.7275),
    "Aue": (50.5878, 12.7076),
    "Baku": (40.4093, 49.8671),
    "Belgrade": (44.8176, 20.4569),
    "Bergamo": (45.6983, 9.6773),
    "Bergen": (60.3913, 5.3221),
    "Berlin": (52.5200, 13.4050),
    "Birmingham": (52.4862, -1.8904),  # UK Birmingham
    "Bodø/Glimt": (67.2804, 14.4049),  # Bodø, Norway
    "Bologna": (44.4949, 11.3426),
    "Bournemouth": (50.7192, -1.8808),
    "Brentford": (51.4882, -0.3088),
    "Brugge": (51.2093, 3.2247),
    "Budapest": (47.4979, 19.0402),
    "Burnley": (53.7890, -2.2374),
    "Falmer": (50.8618, -0.0882),  # Brighton/Falmer stadium
    "Genk": (50.9657, 5.4978),
    "Glasgow": (55.8642, -4.2518),
    "Istanbul": (41.0082, 28.9784),
    "Leeds": (53.8008, -1.5491),
    "Leverkusen": (51.0459, 6.9940),
    "Lille": (50.6292, 3.0573),
    "Lisbon": (38.7223, -9.1393),
    "Liverpool": (53.4084, -2.9916),
    "London": (51.5074, -0.1278),
    "Madrid": (40.4168, -3.7038),
    "Manchester": (53.4808, -2.2426),
    "Melbourne": (-37.8136, 144.9631),
    "Mexico City": (19.4326, -99.1332),
    "Milano": (45.4642, 9.1900),
    "Monaco": (43.7384, 7.4246),
    "Montreal": (45.5017, -73.5673),
    "Montréal": (45.5017, -73.5673),
    "New York City": (40.7128, -74.0060),
    "Newcastle-upon-Tyne": (54.9783, -1.6178),
    "Nottingham": (52.9548, -1.1581),
    "Paris": (48.8566, 2.3522),
    "Piraeus": (37.9427, 23.6465),
    "Plzen": (49.7384, 13.3736),
    "Ponce": (18.0111, -66.6141),  # Puerto Rico
    "Razgrad": (43.5239, 26.5240),
    "San Juan": (18.4655, -66.1057),  # Puerto Rico
    "Stockholm": (59.3293, 18.0686),
    "Stuttgart": (48.7758, 9.1829),
    "Sunderland": (54.9065, -1.3838),
    "Thessaloniki": (40.6401, 22.9444),
    "Torino": (45.0703, 7.6869),
    "Toronto": (43.6532, -79.3832),
    "Toyota Stadium": (33.1546, -96.8350),  # Frisco, TX — home of FC Dallas
    "Vancouver": (49.2827, -123.1207),
    # Canadian cities (province codes not in US state list)
    "Calgary": (51.0447, -114.0719),
    "Edmonton": (53.5461, -113.4938),
    "Winnipeg": (49.8951, -97.1384),
    "Ottawa": (45.4215, -75.6972),
    # US territories
    "Saint Thomas": (18.3419, -64.9307),
    "Vigo": (42.2406, -8.7207),
    "Wolverhampton": (52.5852, -2.1279),
    "Zagreb": (45.8150, 15.9819),
}


def normalize_state(state: str) -> str | None:
    """
    Normalizes a state value to a 2-letter US state code.
    Accepts abbreviations ("GA"), full names ("Georgia"), or DC variants.
    Returns None if the value is not a recognized US state.
    """
    if not state:
        return None
    s = state.strip()
    if len(s) == 2:
        code = s.upper()
        return code if code in _US_STATE_CODES else None
    return _STATE_NAME_TO_CODE.get(s.lower())


def zip_to_coords(zip_code: str) -> tuple[float, float] | None:
    """
    Returns (lat, lon) for a zip code using the local ss_zip_codes table.
    Returns None if the zip is not found.
    """
    row = SportsScheduleZipCode.query.get(zip_code.strip().zfill(5))
    if row is None:
        row = SportsScheduleZipCode.query.get(zip_code.strip())
    if row is None:
        return None
    return (row.lat, row.lon)


def citystate_to_coords(city: str, state: str) -> tuple[float, float] | None:
    """
    Returns (lat, lon) for a city/state pair.
    - For US cities: normalizes state to a 2-letter code, checks ss_geocode_cache, falls back to Nominatim.
    - For international cities (blank or non-US state): checks the hardcoded _INTERNATIONAL_CITY_COORDS dict.
    Returns None if coordinates cannot be determined.
    """
    city = city.strip()
    normalized_state = normalize_state(state)

    if normalized_state is None:
        # Check if city string contains "City, StateName" (e.g. "Houston, Texas")
        if "," in city:
            parts = city.split(",", 1)
            maybe_city = parts[0].strip()
            maybe_state = normalize_state(parts[1].strip())
            if maybe_state:
                return citystate_to_coords(maybe_city, maybe_state)
        # International or unknown — try the hardcoded dict
        return _INTERNATIONAL_CITY_COORDS.get(city)

    state = normalized_state

    cached = SportsScheduleGeocodeCache.query.filter_by(city=city, state=state).first()
    if cached is not None:
        if cached.lat is None:
            return None
        return (cached.lat, cached.lon)

    coords = _nominatim_lookup(city, state)

    entry = SportsScheduleGeocodeCache(
        city=city,
        state=state,
        lat=coords[0] if coords else None,
        lon=coords[1] if coords else None,
    )
    try:
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return coords


def _nominatim_lookup(city: str, state: str) -> tuple[float, float] | None:
    query = f"{city}, {state}, USA"
    try:
        time.sleep(1.1)  # Nominatim rate limit: 1 request/second
        location = _geolocator.geocode(query, timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except Exception as e:
        logger.warning(f"Nominatim geocode failed for '{query}': {e}")
    return None


def nearby_states(lat: float, lon: float, radius_miles: float) -> list[str]:
    """
    Returns a list of state_ids that have at least one zip code within
    radius_miles of (lat, lon). Used to pre-filter DoltHub queries by state
    before doing precise Python-side distance filtering.
    """
    # Convert radius to a rough lat/lon bounding box to narrow the DB query
    delta_lat = radius_miles / 69.0
    delta_lon = radius_miles / (69.0 * abs(__import__("math").cos(__import__("math").radians(lat))) or 1)

    lat_min = lat - delta_lat
    lat_max = lat + delta_lat
    lon_min = lon - delta_lon
    lon_max = lon + delta_lon

    rows = (
        db.session.query(SportsScheduleZipCode.state_id)
        .filter(
            SportsScheduleZipCode.lat >= lat_min,
            SportsScheduleZipCode.lat <= lat_max,
            SportsScheduleZipCode.lon >= lon_min,
            SportsScheduleZipCode.lon <= lon_max,
        )
        .distinct()
        .all()
    )

    return [r.state_id for r in rows]


def filter_rows_by_distance(
    rows: list[dict],
    user_lat: float,
    user_lon: float,
    radius_miles: float,
    city_key: str = "home_city",
    state_key: str = "home_state",
) -> list[dict]:
    """
    Filters a list of event dicts to only those within radius_miles of (user_lat, user_lon).
    Geocodes each unique city/state via the cache as needed.
    """
    user_coords = (user_lat, user_lon)
    coord_cache: dict[tuple[str, str], tuple[float, float] | None] = {}
    filtered = []

    for row in rows:
        city = (row.get(city_key) or "").strip()
        state = (row.get(state_key) or "").strip()
        if not city:
            continue

        key = (city, state)
        if key not in coord_cache:
            coord_cache[key] = citystate_to_coords(city, state)

        coords = coord_cache[key]
        if coords is None:
            continue

        if geodesic(user_coords, coords).miles <= radius_miles:
            filtered.append(row)

    return filtered
