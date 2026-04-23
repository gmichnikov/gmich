"""Weather module — Open-Meteo geocoding + forecast fetch."""

import logging

import requests

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes → human-readable label
_WMO_LABELS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Icy fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight showers",
    81: "Moderate showers",
    82: "Violent showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm w/ hail",
    99: "Thunderstorm w/ heavy hail",
}


def _wmo_label(code):
    if code is None:
        return "Unknown"
    return _WMO_LABELS.get(int(code), f"Code {code}")


def geocode_location(query: str) -> dict | None:
    """
    Resolve a city name or ZIP to lat/lon via Open-Meteo Geocoding API.

    Returns {"lat": float, "lon": float, "label": str} or None on failure.
    """
    try:
        resp = requests.get(
            GEOCODE_URL,
            params={"name": query, "count": 1, "language": "en", "format": "json"},
            timeout=5,
        )
        resp.raise_for_status()
        results = resp.json().get("results")
        if not results:
            logger.info("daily_email geocode: no results for %r", query)
            return None
        r = results[0]
        parts = [r.get("name")]
        if r.get("admin1"):
            parts.append(r["admin1"])
        if r.get("country_code") and r.get("country_code") != "US":
            parts.append(r["country_code"])
        label = ", ".join(p for p in parts if p)
        return {"lat": r["latitude"], "lon": r["longitude"], "label": label}
    except Exception as exc:
        logger.error("daily_email geocode failed for %r: %s", query, exc)
        return None


def fetch_weather(lat: float, lon: float) -> dict | None:
    """
    Fetch a 7-day forecast from Open-Meteo for the given coordinates.

    Returns a dict:
        {
            "today": {
                "high": float, "low": float,
                "precip_pct": int, "condition": str,
                "current_temp": float
            },
            "week": [
                {"date": "YYYY-MM-DD", "high": float, "low": float,
                 "precip_pct": int, "condition": str},
                ...  # 7 entries including today
            ]
        }
    Returns None on any failure.
    """
    try:
        resp = requests.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": (
                    "temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max,weathercode"
                ),
                "current_weather": "true",
                "forecast_days": 7,
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto",
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()

        daily = data.get("daily", {})
        dates = daily.get("time", [])
        highs = daily.get("temperature_2m_max", [])
        lows = daily.get("temperature_2m_min", [])
        precips = daily.get("precipitation_probability_max", [])
        codes = daily.get("weathercode", [])

        current = data.get("current_weather", {})
        current_temp = current.get("temperature")

        if not dates:
            logger.warning("daily_email weather: empty daily data for lat=%s lon=%s", lat, lon)
            return None

        week = []
        for i, d in enumerate(dates):
            week.append({
                "date": d,
                "high": round(highs[i]) if i < len(highs) and highs[i] is not None else None,
                "low": round(lows[i]) if i < len(lows) and lows[i] is not None else None,
                "precip_pct": precips[i] if i < len(precips) else None,
                "condition": _wmo_label(codes[i] if i < len(codes) else None),
            })

        today = week[0] if week else {}
        today_result = {
            "high": today.get("high"),
            "low": today.get("low"),
            "precip_pct": today.get("precip_pct"),
            "condition": today.get("condition"),
            "current_temp": round(current_temp) if current_temp is not None else None,
        }

        return {"today": today_result, "week": week}

    except Exception as exc:
        logger.error("daily_email weather fetch failed (lat=%s lon=%s): %s", lat, lon, exc)
        return None


def render_weather_section(locations: list) -> str | None:
    """
    Fetch weather for each location and render an HTML card.

    locations: list of DailyEmailWeatherLocation model instances.
    Returns an HTML string, or None if all fetches fail.
    """
    cards = []
    for loc in locations[:3]:
        data = fetch_weather(loc.lat, loc.lon)
        if data is None:
            logger.warning("daily_email weather: fetch failed for %r", loc.display_label)
            continue

        today = data["today"]
        week = data["week"]

        today_html = (
            f'<div class="de-weather-today">'
            f'<span class="de-weather-condition">{today["condition"]}</span>'
        )
        if today["current_temp"] is not None:
            today_html += f' &mdash; <span class="de-weather-current">{today["current_temp"]}&deg;F now</span>'
        today_html += (
            f'<span class="de-weather-range"> &nbsp;H:{today["high"]}&deg; / L:{today["low"]}&deg;</span>'
        )
        if today["precip_pct"] is not None:
            today_html += f'<span class="de-weather-precip"> &nbsp;{today["precip_pct"]}% precip</span>'
        today_html += "</div>"

        week_cells = ""
        for day in week:
            short_date = day["date"][5:]  # MM-DD
            week_cells += (
                f'<td class="de-weather-day">'
                f'<div class="de-weather-day-date">{short_date}</div>'
                f'<div class="de-weather-day-cond">{day["condition"][:10]}</div>'
                f'<div class="de-weather-day-range">{day["high"]}&deg;/{day["low"]}&deg;</div>'
                f'</td>'
            )
        week_html = f'<table class="de-weather-week"><tr>{week_cells}</tr></table>'

        cards.append(
            f'<div class="de-module-location">'
            f'<div class="de-module-location-name">{loc.display_label}</div>'
            f"{today_html}"
            f"{week_html}"
            f"</div>"
        )

    if not cards:
        return None

    return (
        '<div class="de-module de-module-weather">'
        '<div class="de-module-header">&#9729; Weather</div>'
        + "".join(cards)
        + "</div>"
    )
