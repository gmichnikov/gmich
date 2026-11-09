"""MCP tools for read-only sports schedule questions."""
import logging
import os
from datetime import datetime, timedelta

from flask import request

from app.projects.mcp.tools import McpToolError, TOOL_HANDLERS
from app.projects.sports_schedule_admin.core.leagues import (
    LEAGUE_DISPLAY_NAMES,
    WOMEN_LEAGUE_CODES,
)
from app.projects.sports_schedules.core.constants import (
    DAYS,
    DIMENSION_LABELS,
    FILTER_ONLY_FIELDS,
    GENDERS,
    HIGH_CARDINALITY_FILTERS,
    LEAGUE_CODES,
    LEVELS,
    SPORTS,
    US_STATE_CODES,
)
from app.projects.sports_schedules.core.run_query import (
    ScheduleQueryError,
    run_schedule_query,
    today_et,
)

logger = logging.getLogger(__name__)

_QUERY_LIMIT = 30
_WINDOW = timedelta(minutes=1)
_PRUNE_EVERY = timedelta(minutes=5)
_BUCKETS: dict[str, list[datetime]] = {}
_LAST_PRUNE = datetime.utcnow()

_DATE_MODES = [
    {"mode": "today", "window": "The Eastern anchor date only."},
    {
        "mode": "this_weekend",
        "window": "Friday–Sunday containing the anchor on Fri/Sat/Sun; otherwise the upcoming Friday–Sunday.",
    },
    {"mode": "next_week", "window": "Anchor through anchor+6 days, inclusive."},
    {"mode": "next_n", "window": "Anchor through anchor+n−1 days. Requires date_n from 1 to 365."},
    {"mode": "last_n", "window": "Anchor−n+1 through the anchor. Requires date_n from 1 to 365."},
    {"mode": "future", "window": "The day after the anchor through 2099-12-31. Excludes today."},
    {"mode": "on_or_after", "window": "date_exact through 2099-12-31."},
    {"mode": "exact", "window": "date_exact only."},
    {"mode": "range", "window": "date_start through date_end."},
]

_NOTES = [
    "Prefer a relative date_mode. The server resolves it in US Eastern time. Do not send anchor_date.",
    "For tomorrow, next month, or a named day, call get_schedule_options and read today, then send exact, on_or_after, or range. There is no month mode and no year mode.",
    "next_week and next_n include today. future starts tomorrow. For upcoming games or when a team plays, use next_n (30, or 365 for a remaining season inside a year). date_n cannot exceed 365, so a longer horizon is on_or_after with today's Eastern date. Do not use future for those questions.",
    "this_weekend is Friday–Sunday: the current weekend on Friday, Saturday, and Sunday, otherwise the upcoming one.",
    "A date_mode is required.",
    "Team, city, and location filters are case-insensitive contains matches and need full names. OKC fails; use Oklahoma City or Thunder. NYC means New York. KC means Kansas City. DC means Washington. LA means Los Angeles. SF means San Francisco. PHX means Phoenix.",
    "One either_team value means that team is home or away. Two values mean they play each other. There is no Celtics-or-Knicks filter; that is two queries.",
    "In New Jersey means home_state NJ, the home team's state. It does not include New Jersey teams playing away.",
    "near needs a 5-digit US zip and a radius of 10, 25, 50, 100, or 250. A city plus a mileage is a home_city contains match, or a request back to the user for a zip. Do not invent a zip.",
    "gender is M or W and is derived from the league. Set it when the user says men's or women's. Do not set it only because the league is already single-gender, such as WNBA. Women's college basketball is gender W, sport basketball, level college.",
    "Times in the rows are Eastern.",
    "An empty rows array means this database had no match. Some smaller college conferences are missing entirely. Do not tell the user that no such game exists.",
    "Default columns are date, time, league, home_team, road_team. For a radius query, also request home_city, home_state, and location.",
    "count true groups by the dimensions and adds # Games. It cannot be combined with near.",
    "limit defaults to 100 and is capped at 500. When truncated is true, say that more matching games were not shown.",
]

_EXAMPLES = (
    'Example: "What games are in NJ this weekend?" -> '
    '{filters:{home_state:["NJ"]}, date_mode:"this_weekend", '
    'dimensions:["date","time","league","home_team","road_team"]}. '
    'Example: "MLB games near 10001 in the next 30 days" -> '
    '{filters:{league:["MLB"], near:{zip:"10001", radius:50}}, date_mode:"next_n", date_n:30, '
    'dimensions:["date","time","league","home_team","road_team","home_city","home_state","location"]}. '
    'Example: "When do the Celtics play the Knicks?" -> '
    '{filters:{either_team:["Celtics","Knicks"]}, date_mode:"next_n", date_n:365}. '
    'Example: "Women\'s college basketball within 50 miles of 07928 in the next two weeks" -> '
    '{filters:{gender:["W"], sport:["basketball"], level:["college"], near:{zip:"07928", radius:50}}, '
    'date_mode:"next_n", date_n:14}.'
)

_SELECTABLE = [name for name in DIMENSION_LABELS if name not in FILTER_ONLY_FIELDS]


def client_ip() -> str:
    """Client address for the rate limit.

    On Heroku the last X-Forwarded-For entry is the one the router appended.
    Earlier entries are client-supplied. With no header, use the socket address.
    """
    forwarded = request.headers.get("X-Forwarded-For", "")
    parts = [part.strip() for part in forwarded.split(",") if part.strip()]
    if parts:
        return parts[-1]
    return request.remote_addr or "unknown"


def prune_rate_buckets(now: datetime | None = None) -> None:
    """Drop timestamps outside the one-minute window and delete empty IP keys."""
    global _LAST_PRUNE
    now = now or datetime.utcnow()
    cutoff = now - _WINDOW
    for key in list(_BUCKETS):
        _BUCKETS[key] = [stamp for stamp in _BUCKETS[key] if stamp > cutoff]
        if not _BUCKETS[key]:
            del _BUCKETS[key]
    _LAST_PRUNE = now


def enforce_query_rate_limit() -> None:
    """Allow 30 query_schedules calls per client IP per rolling minute."""
    global _LAST_PRUNE
    now = datetime.utcnow()
    if now - _LAST_PRUNE > _PRUNE_EVERY:
        prune_rate_buckets(now)
    ip = client_ip()
    recent = [stamp for stamp in _BUCKETS.get(ip, []) if stamp > now - _WINDOW]
    if len(recent) >= _QUERY_LIMIT:
        _BUCKETS[ip] = recent
        raise McpToolError("Rate limit exceeded. Try again in a minute.")
    recent.append(now)
    _BUCKETS[ip] = recent


def reset_rate_buckets() -> None:
    """Clear in-memory buckets. Used by tests."""
    global _LAST_PRUNE
    _BUCKETS.clear()
    _LAST_PRUNE = datetime.utcnow()


def get_schedule_options(**_ignored) -> dict:
    """Allowed values and today's Eastern date. Does not query DoltHub."""
    return {
        "today": today_et(),
        "leagues": [
            {
                "code": code,
                "name": LEAGUE_DISPLAY_NAMES.get(code, code),
                "women": code in WOMEN_LEAGUE_CODES,
            }
            for code in LEAGUE_CODES
        ],
        "sports": list(SPORTS),
        "levels": list(LEVELS),
        "genders": list(GENDERS),
        "days": list(DAYS),
        "states": list(US_STATE_CODES),
        "dimensions": list(_SELECTABLE),
        "filter_only": list(FILTER_ONLY_FIELDS),
        "date_modes": list(_DATE_MODES),
        "radius_options": [10, 25, 50, 100, 250],
        "notes": list(_NOTES),
    }


def query_schedules(**kwargs) -> dict:
    """Run one validated schedule query and return compact rows."""
    enforce_query_rate_limit()
    try:
        result = run_schedule_query(kwargs)
    except McpToolError:
        raise
    except ScheduleQueryError as exc:
        raise McpToolError(str(exc)) from None
    except Exception:
        logger.exception("MCP schedule query failed")
        raise McpToolError("Unable to load schedules. Try again.") from None

    distance_filtered = "near" in (result.applied.get("filters") or {})
    _record_query(result.row_count, distance_filtered)
    return _payload(result, count=_is_count(kwargs.get("count")))


def schedule_mcp_tools() -> list[dict]:
    """Tool definitions built from the same constants as the web UI."""
    low_item = {
        "sport": SPORTS,
        "league": list(LEAGUE_CODES),
        "level": LEVELS,
        "gender": list(GENDERS),
        "day": DAYS,
        "home_state": list(US_STATE_CODES),
    }
    filter_properties = {
        key: {"type": "array", "items": {"type": "string", "enum": values}}
        for key, values in low_item.items()
    }
    for key in HIGH_CARDINALITY_FILTERS:
        filter_properties[key] = {"type": "array", "items": {"type": "string"}}
    filter_properties["either_team"] = {
        "type": "array",
        "items": {"type": "string"},
        "minItems": 1,
        "maxItems": 2,
    }
    filter_properties["near"] = {
        "type": "object",
        "properties": {
            "zip": {"type": "string"},
            "radius": {"type": "number", "enum": [10, 25, 50, 100, 250]},
        },
    }
    description = (
        "Read sports schedule rows (pro, college, and minor league) using the same filters as the site. "
        "You do not need to call get_schedule_options first. Call it when you need today's Eastern date "
        "for exact, on_or_after, or range. "
        + " ".join(_NOTES)
        + " "
        + _EXAMPLES
    )
    return [
        {
            "name": "get_schedule_options",
            "description": (
                "Allowed leagues, states, sports, and date modes for schedule queries, "
                "plus today's Eastern date."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "query_schedules",
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    "dimensions": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(_SELECTABLE)},
                    },
                    "filters": {"type": "object", "properties": filter_properties},
                    "date_mode": {
                        "type": "string",
                        "enum": [item["mode"] for item in _DATE_MODES],
                    },
                    "date_exact": {"type": "string"},
                    "date_start": {"type": "string"},
                    "date_end": {"type": "string"},
                    "date_n": {"type": "integer"},
                    "count": {"type": "boolean"},
                    "limit": {"type": "integer"},
                    "sort_column": {"type": "string"},
                    "sort_dir": {"type": "string", "enum": ["asc", "desc"]},
                },
            },
        },
    ]


def _payload(result, count: bool) -> dict:
    columns = list(result.applied.get("dimensions") or [])
    if count and "# Games" not in columns:
        columns.append("# Games")
    for row in result.rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return {
        "columns": columns,
        "rows": [[row.get(column) for column in columns] for row in result.rows],
        "row_count": result.row_count,
        "truncated": result.truncated,
        "date_range_used": result.date_range_used,
        "applied": result.applied,
    }


def _is_count(value) -> bool:
    if value is True or value == 1:
        return True
    if isinstance(value, str) and value.strip().lower() in ("true", "1", "yes"):
        return True
    return False


def _record_query(row_count: int, distance_filtered: bool) -> None:
    """Log the call. A logging failure still leaves the rows to return."""
    try:
        from app import db
        from app.models import LogEntry

        db.session.add(LogEntry(
            actor_id=None,
            project="sports_schedules",
            category="MCP Query",
            description=(
                f"MCP query: returned {row_count} row(s). "
                f"distance_filtered={distance_filtered}."
            ),
        ))
        db.session.commit()
    except Exception:
        logger.exception("MCP query log failed")
        try:
            from app import db
            db.session.rollback()
        except Exception:
            pass
    try:
        from posthog import Posthog

        Posthog(
            os.environ.get("POSTHOG_API_KEY", ""),
            host="https://us.i.posthog.com",
            sync_mode=True,
        ).capture(
            "sports_mcp_query",
            distinct_id="mcp",
            properties={
                "row_count": row_count,
                "distance_filtered": distance_filtered,
            },
        )
    except Exception:
        logger.exception("MCP query analytics failed")


TOOL_HANDLERS["get_schedule_options"] = get_schedule_options
TOOL_HANDLERS["query_schedules"] = query_schedules
