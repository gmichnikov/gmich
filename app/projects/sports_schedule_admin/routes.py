from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app.core.admin import admin_required

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
    return render_template("sports_schedule_admin/index.html")
