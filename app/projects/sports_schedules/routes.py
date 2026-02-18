"""
Sports Schedules - Public UI for viewing sports schedules.
No login required for browsing/running queries. Login required for saving.
"""

import json

from flask import Blueprint, jsonify, render_template, request, url_for
from flask_login import current_user

from app import db
from app.core.dolthub_client import DoltHubClient
from app.projects.sports_schedules.core.constants import (
    SAVED_QUERY_CONFIG_MAX_BYTES,
    SAVED_QUERY_LIMIT,
)
from app.projects.sports_schedules.core.query_builder import build_sql
from app.projects.sports_schedules.core.sample_queries import SAMPLE_QUERIES
from app.projects.sports_schedules.models import SportsScheduleSavedQuery

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
        is_authenticated=current_user.is_authenticated,
        login_url=url_for("auth.login"),
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


@sports_schedules_bp.route("/api/saved-queries", methods=["GET"])
def api_saved_queries_list():
    """List sample queries (everyone) and user's saved queries (if logged in)."""
    samples = [
        {"id": s["id"], "name": s["name"], "config": s["config"]}
        for s in SAMPLE_QUERIES
    ]
    user_queries = []
    if current_user.is_authenticated:
        rows = (
            SportsScheduleSavedQuery.query.filter_by(user_id=current_user.id)
            .order_by(SportsScheduleSavedQuery.created_at.desc())
            .limit(SAVED_QUERY_LIMIT + 1)
            .all()
        )
        for q in rows[: SAVED_QUERY_LIMIT]:
            config = json.loads(q.config) if isinstance(q.config, str) else q.config
            user_queries.append(
                {
                    "id": q.id,
                    "name": q.name,
                    "config": config,
                    "created_at": q.created_at.isoformat() if q.created_at else None,
                }
            )
    return jsonify({"samples": samples, "user_queries": user_queries})


@sports_schedules_bp.route("/api/saved-queries", methods=["POST"])
def api_saved_queries_create():
    """Create a saved query. Requires login."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid query config"}), 400

    name = (data.get("name") or "").strip()
    config = data.get("config")

    if not name:
        return jsonify({"error": "Name is required"}), 400
    if len(name) > 100:
        return jsonify({"error": "Name must be 100 characters or less"}), 400
    if config is None:
        return jsonify({"error": "Invalid query config"}), 400

    config_str = json.dumps(config) if isinstance(config, dict) else str(config)
    if len(config_str.encode("utf-8")) > SAVED_QUERY_CONFIG_MAX_BYTES:
        return jsonify({"error": "Invalid query config"}), 400

    count = SportsScheduleSavedQuery.query.filter_by(user_id=current_user.id).count()
    if count >= SAVED_QUERY_LIMIT:
        return jsonify(
            {
                "error": "Saved query limit (20) reached. Delete one to save a new query."
            }
        ), 400

    saved = SportsScheduleSavedQuery(
        user_id=current_user.id,
        name=name,
        config=config_str,
    )
    db.session.add(saved)
    db.session.commit()

    return (
        jsonify(
            {
                "id": saved.id,
                "name": saved.name,
                "config": json.loads(saved.config),
                "created_at": saved.created_at.isoformat() if saved.created_at else None,
            }
        ),
        201,
    )


@sports_schedules_bp.route("/api/saved-queries/<int:query_id>", methods=["DELETE"])
def api_saved_queries_delete(query_id):
    """Delete a saved query. Must own it."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401
    q = SportsScheduleSavedQuery.query.get(query_id)
    if not q:
        return "", 404
    if q.user_id != current_user.id:
        return "", 403
    db.session.delete(q)
    db.session.commit()
    return "", 204
