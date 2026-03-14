"""
Convert saved query config to URL params for "View full results" links.
Uses config_to_params to resolve relative date modes with the given anchor.
"""
import urllib.parse

from app.projects.sports_schedules.core.sample_queries import config_to_params


def config_to_url_params(
    config: dict, base_url: str | None = None, anchor_date: str | None = None
) -> str:
    """
    Convert config to query string matching _parse_query_params() expectations.
    Pass anchor_date (YYYY-MM-DD) so "View full results" links use the same
    Thursday anchor as the digest for relative date modes.

    Returns:
        Full URL like {base_url}/sports-schedules?dimensions=... if base_url set,
        or just ?dimensions=... if base_url omitted.
    """
    params = config_to_params(config, anchor_date=anchor_date)

    # Build flat dict for urlencode
    qdict = {}

    if params.get("dimensions"):
        qdict["dimensions"] = params["dimensions"]

    filters = params.get("filters") or {}
    for col in ("sport", "league", "level", "day", "home_state", "home_team", "road_team", "location", "home_city"):
        vals = filters.get(col)
        if vals and isinstance(vals, list):
            qdict[col] = ",".join(str(v) for v in vals if v)
        elif vals and not isinstance(vals, list):
            qdict[col] = str(vals)

    # either_team -> either_team_1, either_team_2
    et = filters.get("either_team") or []
    if isinstance(et, str):
        et = [et] if et else []
    et1 = et[0] if len(et) > 0 else ""
    et2 = et[1] if len(et) > 1 else ""
    if et1 or et2:
        qdict["either_team_1"] = et1
        qdict["either_team_2"] = et2

    for key in ("date_mode", "date_exact", "date_start", "date_end", "date_year", "anchor_date"):
        val = params.get(key)
        if val:
            qdict[key] = str(val)

    if params.get("date_n") is not None:
        qdict["date_n"] = str(params["date_n"])

    qdict["count"] = "1" if params.get("count") else "0"
    qdict["limit"] = str(params.get("limit", 500))
    if params.get("sort_column"):
        qdict["sort_column"] = params["sort_column"]
    qdict["sort_dir"] = params.get("sort_dir") or "asc"

    query_string = urllib.parse.urlencode(qdict, doseq=False)

    if base_url:
        base = base_url.rstrip("/")
        return f"{base}/sports-schedules?{query_string}"
    return f"?{query_string}"
