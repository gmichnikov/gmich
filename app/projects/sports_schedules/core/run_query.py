"""
Run a sports-schedule query for callers that are not the web form.

Validates filters strictly, anchors relative dates in US Eastern time, and
reuses config_to_params, the distance filter, and build_sql.
"""
import copy
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.dolthub_client import DoltHubClient
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
    LOW_CARDINALITY_OPTIONS,
    SPORTS,
    US_STATE_CODES,
)
from app.projects.sports_schedules.core.distance_prepare import (
    apply_post_sql_distance,
    prepare_distance_filter,
)
from app.projects.sports_schedules.core.geocode import GeocodeBudgetExceeded
from app.projects.sports_schedules.core.nl_prompt import STATE_NAME_TO_CODE
from app.projects.sports_schedules.core.query_builder import build_sql
from app.projects.sports_schedules.core.sample_queries import config_to_params

logger = logging.getLogger(__name__)

_EASTERN = ZoneInfo("America/New_York")
_FAR_DATE = date(2099, 12, 31)
_DATE_MODES = (
    "today",
    "this_weekend",
    "next_week",
    "next_n",
    "last_n",
    "future",
    "on_or_after",
    "exact",
    "range",
)
_DEFAULT_DIMENSIONS = ["date", "time", "league", "home_team", "road_team"]
_RADII = (10, 25, 50, 100, 250)
_GEOCODE_MAX_SECONDS = 15
_LOAD_ERROR = "Unable to load schedules. Try again."
_GEOCODE_ERROR = (
    "This radius search needs geocoding that would time out. Try again shortly."
)

_GENDER_ALIASES = {
    "m": "M",
    "men": "M",
    "mens": "M",
    "male": "M",
    "w": "W",
    "women": "W",
    "womens": "W",
    "ladies": "W",
    "female": "W",
}

_LOW_CARD_KEYS = tuple(LOW_CARDINALITY_OPTIONS.keys())
_KNOWN_FILTERS = set(_LOW_CARD_KEYS) | set(HIGH_CARDINALITY_FILTERS) | {
    "either_team",
    "near",
}
_SELECTABLE_DIMENSIONS = [
    name for name in DIMENSION_LABELS if name not in FILTER_ONLY_FIELDS
]


class ScheduleQueryError(Exception):
    """Failure whose message is safe to show to a model or a user."""


@dataclass
class ScheduleQueryResult:
    rows: list
    row_count: int
    truncated: bool
    date_range_used: dict
    applied: dict
    sql: str


def today_et(now: datetime | None = None) -> str:
    """Eastern calendar date the runner uses as the relative-date anchor."""
    current = now if now is not None else datetime.now(_EASTERN)
    if current.tzinfo is None:
        current = current.replace(tzinfo=_EASTERN)
    return current.astimezone(_EASTERN).date().isoformat()


def run_schedule_query(arguments: dict | None) -> ScheduleQueryResult:
    """
    Validate arguments, query DoltHub, and return rows.

    Raises ScheduleQueryError for a bad filter, a missing zip, a geocode timeout,
    or a data-load failure. The load-failure message never includes the upstream error.
    """
    arguments = arguments or {}
    if not isinstance(arguments, dict):
        raise ScheduleQueryError("Query arguments must be an object.")

    count = _as_bool(arguments.get("count"))
    requested_limit = _as_limit(arguments.get("limit"))
    dimensions = _dimensions(arguments.get("dimensions"), count)
    sort_column, sort_dir = _sort(arguments, dimensions, count)
    date_mode, date_exact, date_start, date_end, date_n = _dates(arguments)
    filters, radius_used = _filters(arguments.get("filters"), count)

    config = {
        "dimensions": dimensions,
        "filters": copy.deepcopy(filters),
        "date_mode": date_mode,
        "date_exact": date_exact,
        "date_start": date_start,
        "date_end": date_end,
        "date_n": date_n,
        "count": count,
        "limit": requested_limit,
        "sort_column": sort_column,
        "sort_dir": sort_dir or "asc",
    }
    anchor = today_et()
    params = config_to_params(config, anchor_date=anchor)
    date_range_used = _date_bounds(params)
    applied = {
        "dimensions": list(dimensions),
        "filters": filters,
        "date_mode": date_mode,
        "limit": requested_limit,
    }
    if radius_used is not None:
        applied["radius_used"] = radius_used

    dpr = prepare_distance_filter(params)
    if dpr.error:
        raise ScheduleQueryError(dpr.error)
    if dpr.early_empty:
        return ScheduleQueryResult(
            rows=[],
            row_count=0,
            truncated=False,
            date_range_used=date_range_used,
            applied=applied,
            sql="",
        )

    if dpr.distance_filter_active:
        sql_limit = min(max(requested_limit * 2, 500), 2000)
    else:
        sql_limit = requested_limit + 1
    params["limit"] = sql_limit

    sql, err = build_sql(params)
    if err:
        raise ScheduleQueryError(err)

    result = DoltHubClient().execute_sql(sql)
    if not isinstance(result, dict) or "error" in result:
        logger.error("Schedule query failed to load: %s", (result or {}).get("error"))
        raise ScheduleQueryError(_LOAD_ERROR)

    raw_rows = result.get("rows") or []
    try:
        rows = apply_post_sql_distance(
            raw_rows,
            params,
            dpr,
            max_seconds=_GEOCODE_MAX_SECONDS if dpr.distance_filter_active else None,
        )
    except GeocodeBudgetExceeded:
        raise ScheduleQueryError(_GEOCODE_ERROR) from None

    if dpr.distance_filter_active:
        truncated = len(raw_rows) == sql_limit or len(rows) > requested_limit
    else:
        truncated = len(rows) > requested_limit
    rows = rows[:requested_limit]
    return ScheduleQueryResult(
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        date_range_used=date_range_used,
        applied=applied,
        sql=sql or "",
    )


def _dimensions(raw, count: bool) -> list[str]:
    if raw is None:
        names = list(_DEFAULT_DIMENSIONS)
    else:
        names = _as_list(raw)
    if not names:
        if count:
            return []
        raise ScheduleQueryError(
            "Select at least one dimension, or set count to true."
        )
    cleaned = []
    for name in names:
        token = str(name).strip()
        if not token:
            continue
        if token not in _SELECTABLE_DIMENSIONS:
            allowed = ", ".join(_SELECTABLE_DIMENSIONS)
            raise ScheduleQueryError(f"Unknown dimension '{token}'. Allowed: {allowed}.")
        if token not in cleaned:
            cleaned.append(token)
    if not cleaned and not count:
        raise ScheduleQueryError(
            "Select at least one dimension, or set count to true."
        )
    return cleaned


def _sort(arguments: dict, dimensions: list[str], count: bool) -> tuple[str, str]:
    sort_column = str(arguments.get("sort_column") or "").strip()
    sort_dir = str(arguments.get("sort_dir") or "").strip().lower()
    if sort_dir and sort_dir not in ("asc", "desc"):
        raise ScheduleQueryError("sort_dir must be asc or desc.")
    if not sort_column:
        return "", sort_dir
    allowed = set(dimensions)
    if count:
        allowed.add("# Games")
    if sort_column not in allowed:
        raise ScheduleQueryError(
            f"sort_column '{sort_column}' is not one of the selected dimensions."
        )
    return sort_column, sort_dir or "asc"


def _dates(arguments: dict) -> tuple[str, str, str, str, int | None]:
    date_mode = str(arguments.get("date_mode") or "").strip()
    if date_mode not in _DATE_MODES:
        modes = ", ".join(_DATE_MODES)
        if not date_mode:
            raise ScheduleQueryError(f"date_mode is required. Use one of: {modes}.")
        raise ScheduleQueryError(f"Unknown date_mode '{date_mode}'. Use one of: {modes}.")

    date_exact = ""
    date_start = ""
    date_end = ""
    date_n = None
    if date_mode in ("exact", "on_or_after"):
        date_exact = _require_ymd(arguments.get("date_exact"), "date_exact")
    elif date_mode == "range":
        date_start = _require_ymd(arguments.get("date_start"), "date_start")
        date_end = _require_ymd(arguments.get("date_end"), "date_end")
        if date_start > date_end:
            raise ScheduleQueryError("Start date must be before or equal to end date.")
    elif date_mode in ("next_n", "last_n"):
        date_n = _as_date_n(arguments.get("date_n"))
    return date_mode, date_exact, date_start, date_end, date_n


def _filters(raw, count: bool) -> tuple[dict, int | None]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise ScheduleQueryError("filters must be an object.")
    unknown = [key for key in raw if key not in _KNOWN_FILTERS]
    if unknown:
        raise ScheduleQueryError(f"Unknown filter '{unknown[0]}'.")

    filters: dict = {}
    for key in _LOW_CARD_KEYS:
        if key not in raw or raw[key] in (None, "", []):
            continue
        filters[key] = _low_cardinality(key, raw[key])

    for key in HIGH_CARDINALITY_FILTERS:
        if key not in raw or raw[key] in (None, "", []):
            continue
        values = [str(item).strip() for item in _as_list(raw[key]) if str(item).strip()]
        if values:
            filters[key] = values

    if "either_team" in raw and raw["either_team"] not in (None, "", []):
        teams = [str(item).strip() for item in _as_list(raw["either_team"]) if str(item).strip()]
        if len(teams) > 2:
            raise ScheduleQueryError(
                "either_team accepts one team, or two teams that play each other. "
                "More than two teams is not a matchup. Run a separate query for each team."
            )
        if teams:
            filters["either_team"] = teams

    radius_used = None
    if "near" in raw and raw["near"] not in (None, "", {}):
        filters["near"], radius_used = _near(raw["near"])

    _reject_gender_league_contradiction(filters)
    if count and "near" in filters:
        raise ScheduleQueryError(
            "Distance counts are not supported. Request the rows instead."
        )
    return filters, radius_used


def _low_cardinality(key: str, raw) -> list[str]:
    if key == "gender":
        lookup = _GENDER_ALIASES
        allowed = ", ".join(GENDERS)
    elif key == "home_state":
        lookup = {_fold(code): code for code in US_STATE_CODES}
        for name, code in STATE_NAME_TO_CODE.items():
            lookup[_fold(name)] = code
        allowed = ", ".join(US_STATE_CODES)
    elif key == "league":
        lookup = {}
        for code in LEAGUE_CODES:
            lookup[_fold(code)] = code
            display = LEAGUE_DISPLAY_NAMES.get(code, code)
            lookup[_fold(display)] = code
            stripped = re.sub(r"\s*\([^)]*\)\s*$", "", display).strip()
            if stripped:
                lookup[_fold(stripped)] = code
        allowed = ", ".join(LEAGUE_CODES)
    elif key == "sport":
        lookup = {_fold(value): value for value in SPORTS}
        allowed = ", ".join(SPORTS)
    elif key == "level":
        lookup = {_fold(value): value for value in LEVELS}
        allowed = ", ".join(LEVELS)
    else:
        lookup = {_fold(value): value for value in DAYS}
        allowed = ", ".join(DAYS)

    chosen = []
    for item in _as_list(raw):
        token = str(item).strip()
        if not token:
            continue
        canon = lookup.get(_fold(token))
        if canon is None:
            raise ScheduleQueryError(f"Unknown {key} '{token}'. Allowed: {allowed}.")
        if canon not in chosen:
            chosen.append(canon)
    if not chosen:
        raise ScheduleQueryError(f"{key} needs at least one value.")
    return chosen


def _reject_gender_league_contradiction(filters: dict) -> None:
    genders = filters.get("gender") or []
    leagues = filters.get("league") or []
    if not leagues or genders not in (["W"], ["M"]):
        return
    women = set(WOMEN_LEAGUE_CODES)
    if genders == ["W"] and all(code not in women for code in leagues):
        raise ScheduleQueryError(
            f"gender W does not apply to league {', '.join(leagues)}. "
            "Those leagues are men's. Leave gender unset, or pick a women's league."
        )
    if genders == ["M"] and all(code in women for code in leagues):
        raise ScheduleQueryError(
            f"gender M does not apply to league {', '.join(leagues)}. "
            "Those leagues are women's. Leave gender unset, or pick a men's league."
        )


def _near(raw) -> tuple[dict, int]:
    if not isinstance(raw, dict):
        raise ScheduleQueryError("near must be an object with zip and radius.")
    zip_code = str(raw.get("zip") or "").strip()
    if not re.fullmatch(r"\d{5}", zip_code):
        raise ScheduleQueryError("near.zip must be a 5-digit US zip code.")
    try:
        miles = float(raw.get("radius"))
    except (TypeError, ValueError):
        raise ScheduleQueryError("near.radius must be a number of miles.")
    if miles <= 0:
        raise ScheduleQueryError("near.radius must be greater than 0.")
    snapped = min(_RADII, key=lambda option: (abs(option - miles), -option))
    return {"zip": zip_code, "radius": snapped}, snapped


def _date_bounds(params: dict) -> dict:
    """The window build_sql will apply, after config_to_params has set the anchor."""
    mode = params.get("date_mode") or ""
    anchor = _parse_ymd(params.get("anchor_date"))
    if mode in ("exact", "today"):
        start = end = _parse_ymd(params.get("date_exact")) or anchor
    elif mode == "on_or_after":
        start = _parse_ymd(params.get("date_exact")) or anchor
        end = _FAR_DATE
    elif mode in ("this_weekend", "range"):
        start = _parse_ymd(params.get("date_start"))
        end = _parse_ymd(params.get("date_end"))
    elif mode == "future":
        start = anchor + timedelta(days=1) if anchor else None
        end = _FAR_DATE
    elif mode == "next_week":
        start = anchor
        end = anchor + timedelta(days=6) if anchor else None
    elif mode == "next_n":
        n = int(params.get("date_n"))
        start = anchor
        end = anchor + timedelta(days=n - 1) if anchor else None
    elif mode == "last_n":
        n = int(params.get("date_n"))
        end = anchor
        start = anchor - timedelta(days=n - 1) if anchor else None
    else:
        start = end = None
    if start is None or end is None:
        raise ScheduleQueryError("Could not resolve the date window.")
    return {"start": start.isoformat(), "end": end.isoformat()}


def _as_list(raw) -> list:
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return list(raw)
    raise ScheduleQueryError("Expected a string or a list.")


def _as_bool(value) -> bool:
    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, str):
        token = value.strip().lower()
        if token in ("true", "1", "yes"):
            return True
        if token in ("false", "0", "no", ""):
            return False
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise ScheduleQueryError("count must be true or false.")


def _as_limit(value) -> int:
    if value is None or value == "":
        return 100
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ScheduleQueryError("limit must be an integer.")
    return max(1, min(500, number))


def _as_date_n(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ScheduleQueryError("date_n must be an integer from 1 to 365.")
    if number < 1 or number > 365:
        raise ScheduleQueryError("date_n must be an integer from 1 to 365.")
    return number


def _require_ymd(value, field_name: str) -> str:
    parsed = _parse_ymd(value)
    if parsed is None:
        raise ScheduleQueryError(f"{field_name} must be YYYY-MM-DD.")
    return parsed.isoformat()


def _parse_ymd(value) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _fold(token: str) -> str:
    return token.strip().lower().replace("’", "'").replace("'", "")
