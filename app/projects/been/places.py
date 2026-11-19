"""OpenStreetMap place search via the public Photon geocoder."""

import requests

from app.projects.been.parsing import VisitInputError

PHOTON_URL = "https://photon.komoot.io/api/"
USER_AGENT = "gmich-been/1.0 (personal travel map)"
_REGION_VALUES = {"country", "state", "province"}
_REGION_TYPES = {"country", "state"}
_PLACE_FIELDS = (
    "name",
    "kind",
    "lat",
    "lng",
    "country_code",
    "country_name",
    "region_name",
    "city",
    "osm_type",
    "osm_id",
    "osm_key",
    "osm_value",
)


def _subtitle(name, city, region, country):
    parts = []
    for part in (city, region, country):
        if part and part != name and part not in parts:
            parts.append(part)
    return ", ".join(parts)


def _kind(osm_value, place_type):
    if osm_value in _REGION_VALUES or place_type in _REGION_TYPES:
        return "region"
    return "spot"


def _clip(value, limit):
    text = (value or "").strip()
    if not text:
        return None
    return text[:limit]


def normalize_feature(feature):
    """Turn one Photon feature into a place dict, or None when it cannot be saved."""
    if not isinstance(feature, dict):
        return None
    props = feature.get("properties") or {}
    coords = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coords) < 2:
        return None
    name = _clip(props.get("name"), 255)
    if not name:
        return None
    try:
        lng = float(coords[0])
        lat = float(coords[1])
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    osm_value = _clip(props.get("osm_value"), 64)
    place_type = props.get("type") or ""
    country_code = _clip(props.get("countrycode"), 2)
    if country_code:
        country_code = country_code.upper()
        if len(country_code) != 2 or not country_code.isalpha():
            country_code = None
    city = _clip(props.get("city"), 128)
    region_name = _clip(props.get("state"), 128)
    country_name = _clip(props.get("country"), 128)
    osm_id = props.get("osm_id")
    try:
        osm_id = int(osm_id) if osm_id is not None else None
    except (TypeError, ValueError):
        osm_id = None
    return {
        "name": name,
        "kind": _kind(osm_value or "", place_type),
        "lat": lat,
        "lng": lng,
        "country_code": country_code,
        "country_name": country_name,
        "region_name": region_name,
        "city": city,
        "osm_type": _clip(props.get("osm_type"), 8),
        "osm_id": osm_id,
        "osm_key": _clip(props.get("osm_key"), 64),
        "osm_value": osm_value,
        "subtitle": _subtitle(name, city, region_name, country_name),
    }


def clean_place(data):
    """Validate a place dict posted back from search or a paste review."""
    if not isinstance(data, dict):
        raise VisitInputError("Choose a place from the search results.")
    normalized = normalize_feature(
        {
            "properties": {
                "name": data.get("name"),
                "countrycode": data.get("country_code"),
                "country": data.get("country_name"),
                "state": data.get("region_name"),
                "city": data.get("city"),
                "osm_type": data.get("osm_type"),
                "osm_id": data.get("osm_id"),
                "osm_key": data.get("osm_key"),
                "osm_value": data.get("osm_value"),
                "type": "state" if data.get("kind") == "region" else "city",
            },
            "geometry": {"coordinates": [data.get("lng"), data.get("lat")]},
        }
    )
    if normalized is None:
        raise VisitInputError("Choose a place from the search results.")
    # normalize_feature infers kind from osm fields. Honor an explicit kind when
    # it is one of the two stored values, so a saved region stays a region.
    kind = data.get("kind")
    if kind in ("spot", "region"):
        normalized["kind"] = kind
    return {key: normalized[key] for key in _PLACE_FIELDS}


def search_places(query, limit=6):
    text = (query or "").strip()
    if len(text) < 2:
        return []
    response = requests.get(
        PHOTON_URL,
        params={"q": text[:200], "limit": limit, "lang": "en"},
        headers={"User-Agent": USER_AGENT},
        timeout=8,
    )
    response.raise_for_status()
    features = response.json().get("features") or []
    results = []
    for feature in features:
        item = normalize_feature(feature)
        if item:
            results.append(item)
    return results


def build_paste_preview(text, search, limit=30):
    """Geocode paste lines. `search` is called as search(query, limit=1)."""
    from app.projects.been.parsing import parse_paste_line, parse_when

    parsed_lines = []
    for line in (text or "").splitlines():
        parsed = parse_paste_line(line)
        if parsed:
            parsed_lines.append(parsed)
    truncated = len(parsed_lines) > limit
    rows = []
    search_down = False
    for parsed in parsed_lines[:limit]:
        try:
            parse_when(parsed["when"])
        except VisitInputError as exc:
            rows.append({**parsed, "place": None, "error": str(exc)})
            continue
        if search_down:
            rows.append({**parsed, "place": None, "error": "Place search is unavailable."})
            continue
        try:
            results = search(parsed["query"], limit=1)
        except Exception:
            search_down = True
            rows.append({**parsed, "place": None, "error": "Place search is unavailable."})
            continue
        if not results:
            rows.append({**parsed, "place": None, "error": "No match"})
            continue
        rows.append({**parsed, "place": results[0], "error": None})
    return {"rows": rows, "truncated": truncated}
