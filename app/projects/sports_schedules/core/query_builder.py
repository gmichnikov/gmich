"""
Build SQL for Sports Schedules from user selections.
Table: `combined-schedule` in DoltHub.
"""
from datetime import datetime, timedelta

from app.projects.sports_schedules.core.constants import (
    DIMENSION_LABELS,
    LOW_CARDINALITY_OPTIONS,
)

TABLE = "`combined-schedule`"
VALID_DIMENSIONS = set(DIMENSION_LABELS.keys())
HIGH_CARDINALITY_FILTERS = ["home_team", "road_team", "location", "home_city"]

# Allowlist for low-cardinality: column -> set of valid values
_LOW_CARD_ALLOWLIST = {
    col: {opt[0] for opt in opts}
    for col, opts in LOW_CARDINALITY_OPTIONS.items()
}


def _escape_like_value(value: str) -> str:
    """Escape string for use in SQL LIKE: ', %, _."""
    if not value:
        return ""
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "''")
    s = s.replace("%", "\\%")
    s = s.replace("_", "\\_")
    return s


def _parse_date(s: str):
    """Parse YYYY-MM-DD; returns None if invalid."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def build_sql(params: dict) -> tuple[str | None, str | None]:
    """
    Build SQL from user params.
    Returns (sql_string, error_message). sql_string is None if validation fails.
    """
    raw_dims = params.get("dimensions") or []
    if isinstance(raw_dims, str):
        dimensions = [d.strip() for d in raw_dims.split(",") if d.strip()]
    else:
        dimensions = list(raw_dims)
    count = bool(params.get("count"))
    limit = params.get("limit", 500)
    sort_column = params.get("sort_column") or ""
    sort_dir = (params.get("sort_dir") or "asc").lower()
    filters = params.get("filters") or {}
    date_mode = params.get("date_mode") or ""
    date_exact = params.get("date_exact") or ""
    date_start = params.get("date_start") or ""
    date_end = params.get("date_end") or ""
    date_year = params.get("date_year") or ""
    date_n = params.get("date_n")
    anchor_date = params.get("anchor_date") or ""

    # --- Run requirement ---
    if not dimensions and not count:
        return None, "Select at least one dimension or turn on count to run a query."

    # --- Row limit ---
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 500
    if limit < 1 or limit > 5000:
        return None, "Row limit must be between 1 and 5000."
    limit = max(1, min(5000, limit))

    # --- Dimensions allowlist (exclude filter-only fields) ---
    from app.projects.sports_schedules.core.constants import FILTER_ONLY_FIELDS

    valid_dims = []
    for d in dimensions:
        if d in VALID_DIMENSIONS and d not in FILTER_ONLY_FIELDS:
            valid_dims.append(d)
        # else: ignore invalid or filter-only dimension
    if not valid_dims and not count:
        return None, "Select at least one dimension or turn on count to run a query."

    # --- Filters: low-cardinality validation ---
    low_filters = {}
    for col, allowlist in _LOW_CARD_ALLOWLIST.items():
        vals = filters.get(col)
        if not vals:
            continue
        if isinstance(vals, str):
            vals = [v.strip() for v in vals.split(",") if v.strip()]
        else:
            vals = [str(v).strip() for v in vals if v]
        valid_vals = [v for v in vals if v in allowlist]
        if valid_vals:
            low_filters[col] = valid_vals

    # --- Filters: high-cardinality (contains) ---
    high_filters = {}
    for col in HIGH_CARDINALITY_FILTERS:
        val = filters.get(col)
        if val and isinstance(val, str) and val.strip():
            high_filters[col] = _escape_like_value(val.strip())

    # --- Filters: either_team (OR across home/road; 2 values = matchup) ---
    either_team_conditions = []
    either_team_vals = filters.get("either_team")
    if either_team_vals:
        if isinstance(either_team_vals, str):
            either_team_vals = [v.strip() for v in either_team_vals.split(",") if v.strip()]
        else:
            either_team_vals = [str(v).strip() for v in either_team_vals if v]
        for val in either_team_vals:
            if val:
                escaped = _escape_like_value(val)
                either_team_conditions.append(
                    f"(LOWER(`home_team`) LIKE LOWER('%{escaped}%') OR LOWER(`road_team`) LIKE LOWER('%{escaped}%'))"
                )

    # --- Date conditions ---
    date_start_dt = None
    date_end_dt = None

    if date_mode == "exact":
        d = _parse_date(date_exact)
        if d:
            date_start_dt = date_end_dt = d
        # else: no date filter
    elif date_mode == "range":
        ds = _parse_date(date_start)
        de = _parse_date(date_end)
        if ds and de:
            if ds > de:
                return None, "Start date must be before or equal to end date."
            date_start_dt = ds
            date_end_dt = de
    elif date_mode == "year":
        try:
            y = int(date_year)
            date_start_dt = datetime(y, 1, 1).date()
            date_end_dt = datetime(y, 12, 31).date()
        except (TypeError, ValueError):
            pass
    elif date_mode in ("last_week", "last_month", "last_n", "next_week", "next_n"):
        anchor = _parse_date(anchor_date)
        if not anchor:
            # Fallback: use today (server date)
            anchor = datetime.utcnow().date()
        try:
            n = int(date_n) if date_n is not None else 0
        except (TypeError, ValueError):
            n = 0
        if date_mode == "last_week":
            date_end_dt = anchor
            date_start_dt = anchor - timedelta(days=6)
        elif date_mode == "last_month":
            date_end_dt = anchor
            date_start_dt = anchor - timedelta(days=29)
        elif date_mode == "last_n":
            if n <= 0:
                return None, "Number of days must be greater than 0."
            date_end_dt = anchor
            date_start_dt = anchor - timedelta(days=n - 1)
        elif date_mode == "next_week":
            date_start_dt = anchor
            date_end_dt = anchor + timedelta(days=6)
        elif date_mode == "next_n":
            if n <= 0:
                return None, "Number of days must be greater than 0."
            date_start_dt = anchor
            date_end_dt = anchor + timedelta(days=n - 1)

    # --- Build WHERE ---
    conditions = []
    for col, vals in low_filters.items():
        placeholders = ", ".join(f"'{v.replace(chr(39), chr(39)+chr(39))}'" for v in vals)
        conditions.append(f"`{col}` IN ({placeholders})")
    for col, val in high_filters.items():
        conditions.append(f"LOWER(`{col}`) LIKE LOWER('%{val}%')")
    conditions.extend(either_team_conditions)
    if date_start_dt and date_end_dt:
        conditions.append(f"`date` BETWEEN '{date_start_dt}' AND '{date_end_dt}'")
    where = " AND ".join(conditions) if conditions else "1=1"

    # --- Build SELECT ---
    if count:
        if valid_dims:
            sel_cols = [f"`{c}`" for c in valid_dims]
            select = ", ".join(sel_cols) + ", COUNT(*) AS `# Games`"
            group_by = "GROUP BY " + ", ".join(sel_cols)
        else:
            select = "COUNT(*) AS `# Games`"
            group_by = ""
    else:
        sel_cols = [f"`{c}`" for c in valid_dims]
        select = ", ".join(sel_cols)
        group_by = ""

    # --- ORDER BY ---
    if sort_column:
        valid_sort_cols = set(valid_dims)
        if count:
            valid_sort_cols.add("# Games")
        if sort_column in valid_sort_cols:
            dir_sql = "DESC" if sort_dir == "desc" else "ASC"
            order_by = f"ORDER BY `{sort_column}` {dir_sql}"
        else:
            if count and valid_dims:
                order_by = "ORDER BY `# Games` DESC"
            elif valid_dims:
                order_by = f"ORDER BY `{valid_dims[0]}` ASC"
            else:
                order_by = ""
    else:
        if count and valid_dims:
            order_by = "ORDER BY `# Games` DESC"
        elif valid_dims:
            order_by = f"ORDER BY `{valid_dims[0]}` ASC"
        else:
            order_by = ""

    # --- Assemble SQL ---
    parts = [f"SELECT {select}", f"FROM {TABLE}", f"WHERE {where}"]
    if group_by:
        parts.append(group_by)
    if order_by:
        parts.append(order_by)
    parts.append(f"LIMIT {limit}")

    sql = " ".join(parts)
    return sql, None
