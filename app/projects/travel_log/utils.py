"""Travel Log utilities."""

import re
from zoneinfo import ZoneInfo
import timezonefinder
from datetime import datetime


# Tag format: lowercase, hyphens, numbers only. No spaces.
TLOG_TAG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def normalize_tag_name(raw: str) -> str | None:
    """
    Normalize tag input to canonical form: lowercase, hyphens, numbers only.
    - Strips whitespace
    - Lowercases
    - Replaces spaces with hyphens
    - Removes any character not in [a-z0-9-]
    - Collapses multiple hyphens to one
    - Strips leading/trailing hyphens
    Returns None if result is empty or invalid.
    """
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s or len(s) > 64:
        return None
    if not TLOG_TAG_PATTERN.match(s):
        # Single char must be alphanumeric; multi-char can't start/end with hyphen
        return None
    return s


def parse_hex_color(hex_str: str) -> tuple[int, int, int] | None:
    """Parse #rgb or #rrggbb to (r, g, b) 0-255. Returns None if invalid."""
    if not hex_str or not isinstance(hex_str, str):
        return None
    s = hex_str.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6 or not all(c in "0123456789abcdefABCDEF" for c in s):
        return None
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def _linearize(c: float) -> float:
    """sRGB to linear for luminance."""
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(r: int, g: int, b: int) -> float:
    """WCAG relative luminance (0-1). Dark bg < 0.5."""
    rs = _linearize(r / 255)
    gs = _linearize(g / 255)
    bs = _linearize(b / 255)
    return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs


def contrast_text_color(bg_hex: str | None) -> str:
    """
    Return 'light' or 'dark' for best contrast on the given background.
    Light = white text for dark bg; dark = dark text for light bg.
    """
    rgb = parse_hex_color(bg_hex) if bg_hex else None
    if not rgb:
        return "dark"  # default gray bg
    lum = relative_luminance(*rgb)
    return "light" if lum < 0.5 else "dark"


def normalize_hex_color(raw: str) -> str | None:
    """Normalize to #rrggbb or return None if invalid."""
    rgb = parse_hex_color(raw)
    if not rgb:
        return None
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def tag_display_name(name: str) -> str:
    """Convert stored tag name to display form: 'kid-friendly' -> 'Kid friendly'."""
    if not name:
        return ""
    return " ".join(part.capitalize() for part in name.split("-"))


# Max lengths for place detail fields (Google-derived + user-editable)
TLOG_PLACE_DETAIL_MAX = {
    "primary_type": 64,
    "primary_type_display_name": 128,
    "short_formatted_address": 512,
    "addr_locality": 128,
    "addr_admin_area_1": 128,
    "addr_admin_area_2": 255,
    "addr_admin_area_3": 128,
    "addr_country_code": 2,
}

TLOG_PLACE_DETAIL_KEYS = tuple(TLOG_PLACE_DETAIL_MAX.keys())


def _truncate_place_detail_str(value: str | None, max_len: int) -> str | None:
    if not value or not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if len(s) > max_len:
        s = s[:max_len]
    return s


def parse_address_components_for_place_detail(components: list | None) -> dict[str, str | None]:
    """
    Walk Google Places API (New) addressComponents.
    Skip entries with no types. Country uses shortText as ISO alpha-2 when valid.
    """
    out: dict[str, str | None] = {
        "addr_locality": None,
        "addr_admin_area_1": None,
        "addr_admin_area_2": None,
        "addr_admin_area_3": None,
        "addr_country_code": None,
    }
    if not components:
        return out

    type_to_key = (
        ("locality", "addr_locality"),
        ("administrative_area_level_1", "addr_admin_area_1"),
        ("administrative_area_level_2", "addr_admin_area_2"),
        ("administrative_area_level_3", "addr_admin_area_3"),
    )

    for comp in components:
        if not isinstance(comp, dict):
            continue
        types = comp.get("types")
        if not types:
            continue
        types_set = set(types)
        if "country" in types_set:
            code = (comp.get("shortText") or "").strip().upper()
            if len(code) == 2 and code.isalpha():
                out["addr_country_code"] = code
            continue
        for t, key in type_to_key:
            if t in types_set and out[key] is None:
                long_t = (comp.get("longText") or "").strip()
                out[key] = _truncate_place_detail_str(long_t, TLOG_PLACE_DETAIL_MAX[key])
                break

    return out


def extract_place_detail_from_api_place(place: dict | None) -> dict[str, str | None]:
    """Map a Places API place object to our eight nullable detail fields."""
    empty = {k: None for k in TLOG_PLACE_DETAIL_KEYS}
    if not place or not isinstance(place, dict):
        return empty

    addr = parse_address_components_for_place_detail(place.get("addressComponents"))
    ptdn = place.get("primaryTypeDisplayName") or {}
    ptdn_text = ptdn.get("text") if isinstance(ptdn, dict) else None

    return {
        "primary_type": _truncate_place_detail_str(
            place.get("primaryType") if isinstance(place.get("primaryType"), str) else None,
            TLOG_PLACE_DETAIL_MAX["primary_type"],
        ),
        "primary_type_display_name": _truncate_place_detail_str(
            ptdn_text,
            TLOG_PLACE_DETAIL_MAX["primary_type_display_name"],
        ),
        "short_formatted_address": _truncate_place_detail_str(
            place.get("shortFormattedAddress")
            if isinstance(place.get("shortFormattedAddress"), str)
            else None,
            TLOG_PLACE_DETAIL_MAX["short_formatted_address"],
        ),
        **addr,
    }


def parse_place_detail_from_client(data) -> dict[str, str | None]:
    """
    Read optional place detail keys from a form-like mapping (request.form or JSON dict).
    Strips, truncates, validates addr_country_code as two letters.
    """
    result: dict[str, str | None] = {}
    for key in TLOG_PLACE_DETAIL_KEYS:
        max_len = TLOG_PLACE_DETAIL_MAX[key]
        raw = data.get(key) if hasattr(data, "get") else None
        if raw is None:
            result[key] = None
            continue
        if not isinstance(raw, str):
            raw = str(raw)
        s = raw.strip()
        if not s:
            result[key] = None
            continue
        if key == "addr_country_code":
            s = s.upper()[:2]
            result[key] = s if len(s) == 2 and s.isalpha() else None
        else:
            result[key] = s[:max_len] if len(s) > max_len else s
    return result


def get_visited_date_default(lat, lng):
    """
    Default visited_date from lat/lng timezone, or today if unavailable.
    Used for defaulting visited_date when creating entries with lat/lng.
    """
    try:
        tf = timezonefinder.TimezoneFinder()
        tz_name = tf.timezone_at(lat=float(lat), lng=float(lng))
        if tz_name:
            return datetime.now(ZoneInfo(tz_name)).date()
    except Exception:
        pass
    return datetime.utcnow().date()
