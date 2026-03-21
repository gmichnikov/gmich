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
