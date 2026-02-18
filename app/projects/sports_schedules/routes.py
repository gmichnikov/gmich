"""
Sports Schedules - Public UI for viewing sports schedules.
No login required. No database usage.
"""

from flask import Blueprint, jsonify, render_template, request

from app.core.dolthub_client import DoltHubClient
from app.projects.sports_schedules.core.query_builder import build_sql

sports_schedules_bp = Blueprint(
    "sports_schedules",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/projects/sports_schedules/static",
    url_prefix="/sports-schedules",
)


def _parse_query_params():
    """Parse request args into build_sql params."""
    args = request.args
    filters = {}
    for col in ("sport", "league", "level", "day", "home_state"):
        val = args.get(col)
        if val:
            filters[col] = [v.strip() for v in val.split(",") if v.strip()]
    for col in ("home_team", "road_team", "location", "home_city"):
        val = args.get(col)
        if val and val.strip():
            filters[col] = val.strip()
    et1 = args.get("either_team_1", "").strip()
    et2 = args.get("either_team_2", "").strip()
    if et1 or et2:
        filters["either_team"] = [v for v in [et1, et2] if v]
    return {
        "dimensions": args.get("dimensions", ""),
        "filters": filters,
        "date_mode": args.get("date_mode", ""),
        "date_exact": args.get("date_exact", ""),
        "date_start": args.get("date_start", ""),
        "date_end": args.get("date_end", ""),
        "date_year": args.get("date_year", ""),
        "date_n": args.get("date_n", type=int),
        "anchor_date": args.get("anchor_date", ""),
        "count": args.get("count", "0") in ("1", "true", "yes"),
        "limit": args.get("limit", 500, type=int),
        "sort_column": args.get("sort_column", ""),
        "sort_dir": args.get("sort_dir", "asc"),
    }


@sports_schedules_bp.route("/")
def index():
    """Main schedule viewer - query builder UI."""
    from app.projects.sports_schedules.core.constants import (
        DEFAULT_DIMENSIONS,
        DEFAULT_FILTERS,
        DIMENSION_LABELS,
        FIELD_ORDER,
        FILTER_ONLY_FIELDS,
        LOW_CARDINALITY_OPTIONS,
    )
    return render_template(
        "sports_schedules/index.html",
        default_dimensions=DEFAULT_DIMENSIONS,
        default_filters=DEFAULT_FILTERS,
        dimension_labels=DIMENSION_LABELS,
        field_order=FIELD_ORDER,
        filter_only_fields=FILTER_ONLY_FIELDS,
        low_cardinality_options=LOW_CARDINALITY_OPTIONS,
    )


@sports_schedules_bp.route("/api/query")
def api_query():
    """Execute query against DoltHub. Returns {rows, sql} or {error}."""
    params = _parse_query_params()
    sql, err = build_sql(params)
    if err:
        return jsonify({"error": err}), 400

    dolt = DoltHubClient()
    result = dolt.execute_sql(sql)

    if "error" in result:
        return jsonify({"error": "Unable to load data. Please try again."}), 500

    rows = result.get("rows", [])
    return jsonify({"rows": rows, "sql": sql})
