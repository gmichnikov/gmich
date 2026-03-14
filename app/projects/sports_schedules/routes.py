"""
Sports Schedules - Public UI for viewing sports schedules.
No login required for browsing/running queries. Login required for saving.
"""

import json
import logging
import os
from datetime import datetime

from posthog import Posthog
posthog_client = Posthog(os.environ.get("POSTHOG_API_KEY", ""), host="https://us.i.posthog.com", enable_exception_autocapture=True, sync_mode=True)

from flask import Blueprint, jsonify, render_template, request, url_for
from flask_login import current_user

from app import db
from app.core.dolthub_client import DoltHubClient
from app.models import LogEntry
from app.projects.sports_schedules.core.constants import (
    SAVED_QUERY_CONFIG_MAX_BYTES,
    SAVED_QUERY_LIMIT,
)
from app.projects.sports_schedules.core.nl_prompt import build_nl_prompt
from app.projects.sports_schedules.core.nl_service import call_nl_llm
from app.projects.sports_schedules.core.query_builder import build_sql
from app.projects.sports_schedules.core.sample_queries import SAMPLE_QUERIES, config_to_params
from app.projects.sports_schedules.models import (
    SportsScheduleSavedQuery,
    SportsScheduleScheduledDigest,
    SportsScheduleScheduledDigestQuery,
)

logger = logging.getLogger(__name__)


def _require_auth():
    """Return (None, response) if ok, else (error_response, status_code)."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401
    return None, None

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
            filters[col] = [v.strip() for v in val.split(",") if v.strip()]
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
        HIGH_CARDINALITY_FILTERS,
        LOW_CARDINALITY_OPTIONS,
    )
    return render_template(
        "sports_schedules/index.html",
        default_dimensions=DEFAULT_DIMENSIONS,
        default_filters=DEFAULT_FILTERS,
        dimension_labels=DIMENSION_LABELS,
        field_order=FIELD_ORDER,
        filter_only_fields=FILTER_ONLY_FIELDS,
        high_cardinality_filters=HIGH_CARDINALITY_FILTERS,
        low_cardinality_options=LOW_CARDINALITY_OPTIONS,
        is_authenticated=current_user.is_authenticated,
        login_url=url_for("auth.login"),
        credits=current_user.credits if current_user.is_authenticated else 0,
        email_verified=current_user.email_verified if current_user.is_authenticated else False,
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

    db.session.add(LogEntry(
        actor_id=current_user.id if current_user.is_authenticated else None,
        project="sports_schedules",
        category="Query",
        description=f"Ran query: returned {len(rows)} row(s)",
    ))
    db.session.commit()

    distinct_id = str(current_user.id) if current_user.is_authenticated else "anonymous"
    posthog_client.capture("sports_query_run", distinct_id=distinct_id, properties={
        "row_count": len(rows),
        "authenticated": current_user.is_authenticated,
    })

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


def _extract_json_from_content(content: str):
    """Extract first JSON object from LLM response. Strips markdown fences. Returns (parsed_dict, None) or (None, error_msg)."""
    if not content or not content.strip():
        return None, "Empty response"
    s = content.strip()
    # Strip markdown code fences
    if s.startswith("```"):
        lines = s.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        if lines and lines[0].strip().startswith("{"):
            s = "\n".join(lines)
        elif lines:
            s = "\n".join(lines)
        if s.endswith("```"):
            s = s[:-3].rstrip()
    # Find first { and extract matching object by brace counting
    start = s.find("{")
    if start < 0:
        return None, "No JSON object found"
    depth = 0
    in_string = False
    escape = False
    quote_char = None
    end = start
    for i, c in enumerate(s[start:], start):
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if in_string:
            if c == quote_char:
                in_string = False
            continue
        if c in ('"', "'"):
            in_string = True
            quote_char = c
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if depth != 0:
        return None, "Unbalanced braces"
    try:
        return json.loads(s[start : end + 1]), None
    except json.JSONDecodeError as e:
        return None, str(e)


@sports_schedules_bp.route("/api/nl-query", methods=["POST"])
def api_nl_query():
    """Natural language to query config. Requires login, 1 credit per successful query."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401

    data = request.get_json()
    if data is None:
        return jsonify({"error": "Invalid request body"}), 400

    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Question is required"}), 400
    if len(question) > 500:
        return jsonify({"error": "Question must be 500 characters or less"}), 400

    if (current_user.credits or 0) < 1:
        return jsonify({"error": "Insufficient credits"}), 400

    today_ymd = datetime.utcnow().strftime("%Y-%m-%d")
    input_tokens = 0
    output_tokens = 0

    def _log(outcome: str, credit_used: bool = False):
        q_trunc = question[:200] + "..." if len(question) > 200 else question
        desc = f"NL query: '{q_trunc}' → {outcome}"
        if input_tokens or output_tokens:
            desc += f". input_tokens={input_tokens}, output_tokens={output_tokens}"
        if credit_used:
            desc += ". 1 credit used."
        db.session.add(LogEntry(
            actor_id=current_user.id,
            project="sports_schedules",
            category="NL Query",
            description=desc,
        ))

    try:
        prompt = build_nl_prompt(question, today_ymd)
        content, metadata = call_nl_llm(prompt, distinct_id=str(current_user.id))
        input_tokens = metadata.get("input_tokens", 0)
        output_tokens = metadata.get("output_tokens", 0)
    except Exception:
        logger.exception("NL query LLM call failed")
        _log("LLM exception")
        db.session.commit()
        return jsonify({"error": "Natural language search is temporarily unavailable."}), 500

    parsed, parse_err = _extract_json_from_content(content)
    if parsed is None:
        _log("parse error")
        db.session.commit()
        return jsonify({"error": "Could not parse response", "raw": content[:2000]}), 200

    if "error" in parsed:
        _log("refusal")
        db.session.commit()
        return jsonify({"error": parsed["error"]}), 200

    if "config" not in parsed:
        _log("parse error")
        db.session.commit()
        return jsonify({"error": "Could not parse response", "raw": content[:2000]}), 200

    config = parsed["config"]
    params = config_to_params(config, today_ymd)
    sql, err = build_sql(params)
    if err:
        _log("build_sql error")
        db.session.commit()
        return jsonify({"error": "Could not run that query"}), 400

    current_user.credits = (current_user.credits or 0) - 1
    _log("config", credit_used=True)
    db.session.commit()

    posthog_client.capture("sports_nl_query_used", distinct_id=str(current_user.id), properties={
        "question_length": len(question),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "remaining_credits": current_user.credits,
    })

    return jsonify({
        "config": config,
        "remaining_credits": current_user.credits,
    }), 200


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
    db.session.add(LogEntry(
        actor_id=current_user.id,
        project="sports_schedules",
        category="Saved Query",
        description=f'Saved query "{name}"',
    ))
    db.session.commit()

    posthog_client.capture("sports_query_saved", distinct_id=str(current_user.id), properties={"name": name})

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


@sports_schedules_bp.route("/api/digest", methods=["GET"])
def api_digest_get():
    """Get the current user's digest settings. Requires login."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401
    digest = SportsScheduleScheduledDigest.query.filter_by(user_id=current_user.id).first()
    if not digest:
        return jsonify({"digest": None})
    query_ids = [
        dq.saved_query_id
        for dq in sorted(digest.digest_queries, key=lambda dq: dq.sort_order)
    ]
    return jsonify({
        "digest": {
            "id": digest.id,
            "schedule_hour": digest.schedule_hour,
            "enabled": digest.enabled,
            "last_sent_at": digest.last_sent_at.isoformat() if digest.last_sent_at else None,
            "query_ids": query_ids,
        }
    })


@sports_schedules_bp.route("/api/digest", methods=["PUT"])
def api_digest_put():
    """Create or update digest settings. Requires login."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Login required"}), 401
    if not current_user.email_verified:
        return jsonify({"error": "Verify your email to use weekly digests"}), 400
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid request body"}), 400

    schedule_hour = data.get("schedule_hour")
    if schedule_hour is None:
        schedule_hour = 8
    try:
        schedule_hour = int(schedule_hour)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid schedule_hour"}), 400
    if schedule_hour < 5 or schedule_hour > 22:
        return jsonify({"error": "Schedule hour must be 5–22 (5am–10pm)"}), 400

    enabled = data.get("enabled", False)
    query_ids = data.get("query_ids") or []

    if enabled and not query_ids:
        return jsonify({"error": "Select at least one saved query"}), 400

    # Validate each query_id belongs to current user
    valid_ids = []
    if query_ids:
        owned = {
            q.id for q in
            SportsScheduleSavedQuery.query.filter(
                SportsScheduleSavedQuery.id.in_(query_ids),
                SportsScheduleSavedQuery.user_id == current_user.id,
            ).all()
        }
        valid_ids = [qid for qid in query_ids if qid in owned]

    digest = SportsScheduleScheduledDigest.query.filter_by(user_id=current_user.id).first()
    if not digest:
        digest = SportsScheduleScheduledDigest(
            user_id=current_user.id,
            schedule_hour=schedule_hour,
            enabled=enabled,
        )
        db.session.add(digest)
        db.session.flush()
    else:
        digest.schedule_hour = schedule_hour
        digest.enabled = enabled

    # Replace digest queries
    SportsScheduleScheduledDigestQuery.query.filter_by(digest_id=digest.id).delete()
    for i, qid in enumerate(valid_ids):
        dq = SportsScheduleScheduledDigestQuery(
            digest_id=digest.id,
            saved_query_id=qid,
            sort_order=i,
        )
        db.session.add(dq)

    db.session.commit()

    query_ids_out = [
        dq.saved_query_id
        for dq in sorted(digest.digest_queries, key=lambda dq: dq.sort_order)
    ]
    return jsonify({
        "digest": {
            "id": digest.id,
            "schedule_hour": digest.schedule_hour,
            "enabled": digest.enabled,
            "last_sent_at": digest.last_sent_at.isoformat() if digest.last_sent_at else None,
            "query_ids": query_ids_out,
        }
    })
