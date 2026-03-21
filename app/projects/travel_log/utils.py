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
