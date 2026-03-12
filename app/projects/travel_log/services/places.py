"""Google Places API (New) proxy — search_nearby and search_text."""

import logging
import math
import requests

# Types to filter out when no category selected ("other")
UNHELPFUL_TYPES = {"route", "locality", "political", "real_estate_agency"}

# Category → includedTypes (from PRD/INITIAL_SPEC 5.6)
CATEGORY_TYPES = {
    "food": [
        "restaurant", "cafe", "bar", "bakery",
        "coffee_shop", "ice_cream_shop", "meal_takeaway",
    ],
    "shopping": [
        "store", "shopping_mall", "book_store", "clothing_store",
        "grocery_store", "convenience_store",
    ],
    "attractions": [
        "tourist_attraction", "museum", "art_gallery", "historical_landmark",
        "park", "amusement_park", "zoo", "aquarium",
    ],
    "other": None,  # No filter; will filter UNHELPFUL_TYPES client-side
}

FIELD_MASK = (
    "places.displayName,places.formattedAddress,places.location,"
    "places.id,places.types,places.businessStatus"
)


def _distance_m(lat1, lng1, lat2, lng2):
    """Approximate distance in meters (Haversine)."""
    R = 6_371_000  # Earth radius in m
    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lng2 - lng1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _place_to_dict(place, center_lat=None, center_lng=None):
    """Convert API place to simplified dict for frontend."""
    out = {
        "place_id": place.get("id", ""),
        "name": place.get("displayName", {}).get("text", ""),
        "address": place.get("formattedAddress", ""),
        "types": place.get("types", []),
    }
    loc = place.get("location", {})
    lat = loc.get("latitude")
    lng = loc.get("longitude")
    if lat is not None and lng is not None:
        out["lat"] = lat
        out["lng"] = lng
        if center_lat is not None and center_lng is not None:
            out["distance_m"] = round(_distance_m(center_lat, center_lng, lat, lng))
    status = place.get("businessStatus")
    if status:
        out["businessStatus"] = status
    return out


def search_nearby(lat, lng, radius_m=200, included_types=None, api_key=None):
    """
    Nearby Search (New). Returns list of places within radius.
    Filters out businessStatus != OPERATIONAL, sorts by distance.
    """
    from flask import current_app
    key = api_key or current_app.config.get("GOOGLE_PLACES_API_KEY")
    if not key:
        logging.error("GOOGLE_PLACES_API_KEY not configured")
        return []

    payload = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius_m),
            }
        }
    }
    if included_types:
        payload["includedTypes"] = included_types

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    radii = [radius_m] + ([400] if radius_m < 500 else [])
    for attempt, r in enumerate(radii):
        payload["locationRestriction"]["circle"]["radius"] = float(r)
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            logging.exception("Places API searchNearby failed: %s", e)
            return []

        data = resp.json()
        places_raw = data.get("places", [])

        # Exclude closed places; include OPERATIONAL and places without businessStatus (e.g. parks, landmarks)
        closed = {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}
        operational = [p for p in places_raw if p.get("businessStatus") not in closed]
        if not included_types or included_types == "other":
            operational = [p for p in operational if not (set(p.get("types", [])) & UNHELPFUL_TYPES)]

        results = []
        for p in operational:
            d = _place_to_dict(p, lat, lng)
            if "lat" in d:
                results.append(d)
        results.sort(key=lambda x: x.get("distance_m", 999999))

        if len(results) >= 3 or attempt > 0 or radius_m >= 500:
            return results
        radius_m = 400

    return results


def search_text(query, lat=None, lng=None, box_size_m=400, api_key=None):
    """
    Text Search (New). Query with optional location restriction.
    If lat/lng provided: rectangle around point. Otherwise: no location (user includes it in query).
    """
    from flask import current_app
    key = api_key or current_app.config.get("GOOGLE_PLACES_API_KEY")
    if not key:
        logging.error("GOOGLE_PLACES_API_KEY not configured")
        return []

    payload = {"textQuery": query.strip()}
    if lat is not None and lng is not None:
        # Approx meters per degree: lat ~111320, lng ~111320*cos(lat)
        half = box_size_m / 2
        lat_off = half / 111_320
        lng_off = half / (111_320 * math.cos(math.radians(lat)))
        payload["locationRestriction"] = {
            "rectangle": {
                "low": {"latitude": lat - lat_off, "longitude": lng - lng_off},
                "high": {"latitude": lat + lat_off, "longitude": lng + lng_off},
            }
        }

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": FIELD_MASK,
    }

    for attempt in range(2):
        if attempt == 1 and lat is not None and lng is not None:
            box_size_m = min(800, box_size_m * 2)
            half = box_size_m / 2
            lat_off = half / 111_320
            lng_off = half / (111_320 * math.cos(math.radians(lat)))
            payload["locationRestriction"]["rectangle"] = {
                "low": {"latitude": lat - lat_off, "longitude": lng - lng_off},
                "high": {"latitude": lat + lat_off, "longitude": lng + lng_off},
            }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            logging.exception("Places API searchText failed: %s", e)
            return []

        data = resp.json()
        places_raw = data.get("places", [])

        closed = {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}
        operational = [p for p in places_raw if p.get("businessStatus") not in closed]
        results = []
        for p in operational:
            d = _place_to_dict(p, lat, lng)
            results.append(d)
        if lat is not None and lng is not None:
            results.sort(key=lambda x: x.get("distance_m", 999999))

        if len(results) >= 3 or attempt > 0 or lat is None:
            return results

    return results
