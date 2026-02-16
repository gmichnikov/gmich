from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import login_required, current_user
from app.core.admin import admin_required
from app.projects.sports_schedule_admin.core.dolthub_client import DoltHubClient
from app.projects.sports_schedule_admin.core.logic import sync_league_range, clear_league_data
from app.projects.sports_schedule_admin.core.espn_client import ESPNClient
from app.models import LogEntry, db
from datetime import datetime, timedelta

sports_schedule_admin_bp = Blueprint(
    "sports_schedule_admin",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/projects/sports_schedule_admin/static",
)


@sports_schedule_admin_bp.route("/sports-schedule-admin")
@login_required
@admin_required
def index():
    display = ESPNClient.LEAGUE_DISPLAY_NAMES
    leagues = [(code, display.get(code, code)) for code in ESPNClient.LEAGUE_MAP.keys()]
    return render_template("sports_schedule_admin/index.html", leagues=leagues)


@sports_schedule_admin_bp.route("/sports-schedule-admin/api/coverage")
@login_required
@admin_required
def get_coverage():
    """Fetch league coverage stats from DoltHub."""
    dolt = DoltHubClient()
    sql = "SELECT league, sport, MIN(date) as start_date, MAX(date) as end_date, COUNT(*) as count FROM `combined-schedule` GROUP BY league, sport ORDER BY league"
    result = dolt.execute_sql(sql)
    
    if "error" in result:
        return jsonify({"error": result["error"]}), 500
        
    return jsonify(result.get("rows", []))


@sports_schedule_admin_bp.route("/sports-schedule-admin/api/logs")
@login_required
@admin_required
def get_logs():
    """Fetch recent activity logs."""
    logs = LogEntry.query.filter_by(project="sports_admin").order_by(LogEntry.timestamp.desc()).limit(10).all()
    return jsonify([{
        "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "actor": log.actor.email if log.actor else "System",
        "category": log.category,
        "description": log.description,
    } for log in logs])


@sports_schedule_admin_bp.route("/sports-schedule-admin/api/preview")
@login_required
@admin_required
def get_preview():
    """Fetch the most recent 10 games from DoltHub."""
    dolt = DoltHubClient()
    # Assuming there's no 'created_at' in existing schema, we'll just show the 10 latest dates
    sql = "SELECT * FROM `combined-schedule` ORDER BY date DESC, primary_key DESC LIMIT 10"
    result = dolt.execute_sql(sql)
    
    if "error" in result:
        return jsonify({"error": result["error"]}), 500
        
    return jsonify(result.get("rows", []))


@sports_schedule_admin_bp.route("/sports-schedule-admin/api/sync", methods=["POST"])
@login_required
@admin_required
def api_sync():
    """Trigger a manual sync from ESPN to DoltHub."""
    data = request.get_json() or {}
    league = data.get("league")
    start_str = data.get("start_date")
    days = data.get("days", 7)

    if not league or league not in ESPNClient.LEAGUE_MAP:
        return jsonify({"success": False, "error": "Invalid or missing league"}), 400

    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "Invalid start_date (use YYYY-MM-DD)"}), 400

    days = int(days)
    if days < 1 or days > 30:
        return jsonify({"success": False, "error": "Days must be between 1 and 30"}), 400

    end_date = start_date + timedelta(days=days - 1)
    actor_id = current_user.id if current_user else None

    try:
        result = sync_league_range(league, start_date, end_date, actor_id=actor_id)
        return jsonify({
            "success": True,
            "message": f"Synced {result['league']}: {result['upserted']} games upserted.",
            "games_found": result["games_found"],
            "upserted": result["upserted"],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@sports_schedule_admin_bp.route("/sports-schedule-admin/api/clear-league", methods=["POST"])
@login_required
@admin_required
def api_clear_league():
    """Clear data for a league (with optional start date)."""
    data = request.get_json() or {}
    league = data.get("league")
    confirm = data.get("confirm")
    start_str = data.get("start_date")

    if not league or league not in ESPNClient.LEAGUE_MAP:
        return jsonify({"success": False, "error": "Invalid or missing league"}), 400

    if (confirm or "").strip().upper() != league:
        return jsonify({"success": False, "error": "Type the league code to confirm"}), 400

    start_date = None
    if start_str:
        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "Invalid start_date (use YYYY-MM-DD)"}), 400

    actor_id = current_user.id if current_user else None

    try:
        result = clear_league_data(league, start_date=start_date, actor_id=actor_id)
        if result and "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 500
        return jsonify({"success": True, "message": f"Cleared {league} data."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
