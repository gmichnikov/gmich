"""Game-clock display and parsing. Stored values are milliseconds into the period."""

from datetime import datetime
import re

CLOCK_RE = re.compile(r"^(\d{1,3}):([0-5]\d)$")


def format_ms(ms):
    ms = max(0, int(ms or 0))
    total_sec = ms // 1000
    minutes = total_sec // 60
    seconds = total_sec % 60
    return f"{minutes}:{seconds:02d}"


def parse_clock(text):
    """Return milliseconds for M:SS / MM:SS, or None if invalid."""
    if text is None:
        return None
    raw = str(text).strip()
    match = CLOCK_RE.match(raw)
    if not match:
        return None
    minutes = int(match.group(1))
    seconds = int(match.group(2))
    return (minutes * 60 + seconds) * 1000


def displayed_elapsed_ms(game, now=None):
    """Wall-clock math while running; frozen elapsed_ms while paused."""
    now = now or datetime.utcnow()
    elapsed = max(0, int(game.elapsed_ms or 0))
    if not game.clock_running or game.last_resumed_at is None:
        return elapsed
    delta = now - game.last_resumed_at
    extra = int(delta.total_seconds() * 1000)
    return max(0, elapsed + extra)


def iso_utc(dt):
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        return dt.isoformat() + "Z"
    return dt.isoformat()
