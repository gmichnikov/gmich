"""Weather module — Open-Meteo geocoding + forecast fetch."""

import logging
from datetime import date

import requests

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes → (label, emoji)
_WMO_MAP = {
    0:  ("Clear sky",              "☀️"),
    1:  ("Mainly clear",           "🌤️"),
    2:  ("Partly cloudy",          "⛅"),
    3:  ("Overcast",               "☁️"),
    45: ("Fog",                    "🌫️"),
    48: ("Icy fog",                "🌫️"),
    51: ("Light drizzle",          "🌦️"),
    53: ("Moderate drizzle",       "🌦️"),
    55: ("Dense drizzle",          "🌧️"),
    61: ("Slight rain",            "🌧️"),
    63: ("Moderate rain",          "🌧️"),
    65: ("Heavy rain",             "🌧️"),
    71: ("Slight snow",            "🌨️"),
    73: ("Moderate snow",          "🌨️"),
    75: ("Heavy snow",             "❄️"),
    77: ("Snow grains",            "❄️"),
    80: ("Slight showers",         "🌦️"),
    81: ("Moderate showers",       "🌧️"),
    82: ("Violent showers",        "⛈️"),
    85: ("Slight snow showers",    "🌨️"),
    86: ("Heavy snow showers",     "❄️"),
    95: ("Thunderstorm",           "⛈️"),
    96: ("Thunderstorm w/ hail",   "⛈️"),
    99: ("Thunderstorm w/ hail",   "⛈️"),
}


def _wmo_label(code) -> str:
    if code is None:
        return "Unknown"
    return _WMO_MAP.get(int(code), (f"Code {code}", "🌡️"))[0]


def _wmo_emoji(code) -> str:
    if code is None:
        return "🌡️"
    return _WMO_MAP.get(int(code), (None, "🌡️"))[1]


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


def fetch_weather(lat: float, lon: float, user_timezone: str = "auto") -> dict | None:
    """
    Fetch a 7-day forecast from Open-Meteo for the given coordinates.

    user_timezone: IANA timezone string (e.g. "America/New_York"). Passing the
    user's own timezone instead of "auto" ensures all locations are anchored to
    the same calendar day — so "today" means the same date for every location.

    Returns a dict:
        {
            "today": {
                "high": float, "low": float,
                "precip_pct": int, "precip_mm": float,
                "condition": str, "emoji": str,
                "current_temp": float,
                "sunrise": str, "sunset": str,
            },
            "week": [
                {"date": "YYYY-MM-DD", "weekday": "Mon.", "high": float, "low": float,
                 "precip_pct": int, "precip_mm": float, "condition": str, "emoji": str},
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
                    "precipitation_probability_max,precipitation_sum,"
                    "weathercode,sunrise,sunset"
                ),
                "current_weather": "true",
                "forecast_days": 7,
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": user_timezone,
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()

        daily = data.get("daily", {})
        dates       = daily.get("time", [])
        highs       = daily.get("temperature_2m_max", [])
        lows        = daily.get("temperature_2m_min", [])
        precip_pcts = daily.get("precipitation_probability_max", [])
        precip_mms  = daily.get("precipitation_sum", [])
        codes       = daily.get("weathercode", [])
        sunrises    = daily.get("sunrise", [])
        sunsets     = daily.get("sunset", [])

        current = data.get("current_weather", {})
        current_temp = current.get("temperature")

        if not dates:
            logger.warning("daily_email weather: empty daily data for lat=%s lon=%s", lat, lon)
            return None

        week = []
        for i, d in enumerate(dates):
            code = codes[i] if i < len(codes) else None
            # Parse "YYYY-MM-DD" to get abbreviated weekday
            try:
                weekday = date.fromisoformat(d).strftime("%a.")
            except ValueError:
                weekday = ""

            # Sunrise/sunset come back as "YYYY-MM-DDTHH:MM" — keep only HH:MM
            def _time_only(val):
                if val and "T" in val:
                    return val.split("T")[1]
                return val or ""

            week.append({
                "date":        d,
                "weekday":     weekday,
                "high":        round(highs[i]) if i < len(highs) and highs[i] is not None else None,
                "low":         round(lows[i]) if i < len(lows) and lows[i] is not None else None,
                "precip_pct":  precip_pcts[i] if i < len(precip_pcts) else None,
                "precip_mm":   round(precip_mms[i], 1) if i < len(precip_mms) and precip_mms[i] is not None else None,
                "condition":   _wmo_label(code),
                "emoji":       _wmo_emoji(code),
                "sunrise":     _time_only(sunrises[i] if i < len(sunrises) else None),
                "sunset":      _time_only(sunsets[i] if i < len(sunsets) else None),
            })

        today = week[0] if week else {}
        today_result = {
            "high":        today.get("high"),
            "low":         today.get("low"),
            "precip_pct":  today.get("precip_pct"),
            "precip_mm":   today.get("precip_mm"),
            "condition":   today.get("condition"),
            "emoji":       today.get("emoji"),
            "current_temp": round(current_temp) if current_temp is not None else None,
            "sunrise":     today.get("sunrise"),
            "sunset":      today.get("sunset"),
        }

        return {"today": today_result, "week": week}

    except Exception as exc:
        logger.error("daily_email weather fetch failed (lat=%s lon=%s): %s", lat, lon, exc)
        return None


def render_weather_section(locations: list, user_timezone: str = "auto") -> str | None:
    """
    Fetch weather for each location and render an HTML card.

    locations: list of DailyEmailWeatherLocation model instances.
    user_timezone: IANA timezone string passed through to fetch_weather so all
                   locations share the same calendar anchor date.
    Returns an HTML string, or None if all fetches fail.
    """
    cards = []
    for loc in locations[:3]:
        data = fetch_weather(loc.lat, loc.lon, user_timezone=user_timezone)
        if data is None:
            logger.warning("daily_email weather: fetch failed for %r", loc.display_label)
            continue

        today = data["today"]
        week = data["week"]

        # ── Today summary ──
        precip_parts = []
        if today.get("precip_pct") is not None:
            precip_parts.append(f'{today["precip_pct"]}% chance')
        if today.get("precip_mm") is not None and today["precip_mm"] > 0:
            precip_parts.append(f'{today["precip_mm"]} mm')
        precip_str = " &middot; ".join(precip_parts)

        sun_str = ""
        if today.get("sunrise") and today.get("sunset"):
            sun_str = (
                f'<span style="color:#aaa;font-size:11px;">'
                f'&#127751; {today["sunrise"]} &nbsp;&#127747; {today["sunset"]}'
                f'</span>'
            )

        today_html = (
            f'<div style="padding:10px 14px 4px;">'
            f'<span style="font-size:28px;line-height:1;">{today.get("emoji","")}</span>'
            f'<span style="font-size:15px;font-weight:700;margin-left:8px;">{today.get("condition","")}</span>'
        )
        if today.get("current_temp") is not None:
            today_html += f'<span style="color:#555;font-size:14px;margin-left:8px;">{today["current_temp"]}&deg;F now</span>'
        today_html += (
            f'<br><span style="font-size:13px;color:#333;">'
            f'H: {today.get("high","–")}&deg; &nbsp;/&nbsp; L: {today.get("low","–")}&deg;'
        )
        if precip_str:
            today_html += f' &nbsp;&middot;&nbsp; &#x1F4A7; {precip_str}'
        today_html += f'</span>'
        if sun_str:
            today_html += f'<br>{sun_str}'
        today_html += '</div>'

        # ── 7-day strip ──
        week_cells = ""
        for day in week:
            short_date = day["date"][5:]  # MM-DD
            precip_badge = ""
            if day.get("precip_pct") is not None and day["precip_pct"] >= 20:
                precip_badge = (
                    f'<div style="color:#3a7dc9;font-size:10px;">'
                    f'&#x1F4A7;{day["precip_pct"]}%</div>'
                )
            precip_mm_badge = ""
            if day.get("precip_mm") is not None and day["precip_mm"] > 0:
                precip_mm_badge = (
                    f'<div style="color:#3a7dc9;font-size:10px;">{day["precip_mm"]}mm</div>'
                )
            week_cells += (
                f'<td style="text-align:center;padding:6px 3px;border-top:1px solid #f0f0f0;'
                f'vertical-align:top;width:14%;">'
                f'<div style="font-weight:700;font-size:11px;color:#555;">{day["weekday"]}</div>'
                f'<div style="font-size:10px;color:#888;">{short_date}</div>'
                f'<div style="font-size:18px;line-height:1.3;">{day.get("emoji","")}</div>'
                f'<div style="font-size:11px;font-weight:700;color:#333;">'
                f'{day.get("high","–")}&deg;/{day.get("low","–")}&deg;</div>'
                f'{precip_badge}'
                f'{precip_mm_badge}'
                f'</td>'
            )
        week_html = (
            f'<table style="width:100%;border-collapse:collapse;font-size:12px;">'
            f'<tr>{week_cells}</tr></table>'
        )

        cards.append(
            f'<div style="border-bottom:1px solid #f0f0f0;">'
            f'<div style="padding:10px 14px 4px;font-weight:700;font-size:14px;color:#1a1a2e;">'
            f'{loc.display_label}</div>'
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
