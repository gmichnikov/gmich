from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request
from flask_login import login_required, current_user
from app.core.admin import admin_required
from app.projects.sports_schedule_admin.core.dolthub_client import DoltHubClient
from app.models import LogEntry, db
from datetime import datetime

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
    # Fetch recent activity logs from the local DB
    # We'll look for logs with project="sports_admin"
    logs = LogEntry.query.filter_by(project="sports_admin").order_by(LogEntry.timestamp.desc()).limit(10).all()
    
    return render_template("sports_schedule_admin/index.html", logs=logs)


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
