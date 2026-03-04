from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user

from app import db
from app.utils.logging import log_project_visit
from app.projects.reminders.models import Reminder
from app.projects.reminders.email import send_reminder_email

reminders_bp = Blueprint(
    "reminders",
    __name__,
    url_prefix="/reminders",
    template_folder="templates",
    static_folder="static",
    static_url_path="/reminders/static",
)


# --- Helpers ---

def get_reminder_or_404(reminder_id):
    reminder = Reminder.query.get(reminder_id)
    if reminder is None or reminder.user_id != current_user.id:
        abort(404)
    return reminder


def format_remind_at_for_user(dt, user):
    """Convert UTC datetime to user's timezone, formatted for display."""
    if dt is None:
        return ""
    user_tz = ZoneInfo(user.time_zone or "UTC")
    local_dt = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(user_tz)
    return local_dt.strftime("%b %-d, %Y %-I:%M %p")


def parse_remind_at_from_user(dt_string, user):
    """
    Parse a datetime string (from the form, in the user's timezone)
    and return a naive UTC datetime. Returns None if parsing fails.
    """
    try:
        user_tz = ZoneInfo(user.time_zone or "UTC")
        local_dt = datetime.strptime(dt_string, "%Y-%m-%dT%H:%M")
        aware_dt = local_dt.replace(tzinfo=user_tz)
        return aware_dt.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def user_tz_name(user):
    return user.time_zone or "UTC"


# --- Routes ---

@reminders_bp.route("/")
@login_required
def index():
    log_project_visit("reminders", "Reminders")
    now_utc = datetime.utcnow()

    upcoming = (
        Reminder.query
        .filter_by(user_id=current_user.id)
        .filter(Reminder.sent_at.is_(None))
        .filter(Reminder.remind_at > now_utc)
        .order_by(Reminder.remind_at.asc())
        .all()
    )
    past = (
        Reminder.query
        .filter_by(user_id=current_user.id)
        .filter(Reminder.sent_at.isnot(None))
        .order_by(Reminder.sent_at.desc())
        .all()
    )

    credits = current_user.credits or 0
    low_credits = len(upcoming) > credits

    return render_template(
        "reminders/index.html",
        upcoming=upcoming,
        past=past,
        credits=credits,
        low_credits=low_credits,
        format_dt=lambda dt: format_remind_at_for_user(dt, current_user),
    )


@reminders_bp.route("/new")
@login_required
def new():
    prefill_title = request.args.get("title", "")
    prefill_body = request.args.get("body", "")
    return render_template(
        "reminders/new.html",
        prefill_title=prefill_title,
        prefill_body=prefill_body,
        tz_name=user_tz_name(current_user),
    )


@reminders_bp.route("/create", methods=["POST"])
@login_required
def create():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip() or None
    dt_string = request.form.get("remind_at", "").strip()

    if not title:
        flash("Title is required.", "error")
        return render_template(
            "reminders/new.html",
            prefill_title=title,
            prefill_body=body or "",
            tz_name=user_tz_name(current_user),
            error=True,
        )

    remind_at_utc = parse_remind_at_from_user(dt_string, current_user)
    if remind_at_utc is None:
        flash("Please enter a valid date and time.", "error")
        return render_template(
            "reminders/new.html",
            prefill_title=title,
            prefill_body=body or "",
            tz_name=user_tz_name(current_user),
            error=True,
        )

    if remind_at_utc <= datetime.utcnow():
        flash("Reminder time must be in the future.", "error")
        return render_template(
            "reminders/new.html",
            prefill_title=title,
            prefill_body=body or "",
            tz_name=user_tz_name(current_user),
            error=True,
        )

    reminder = Reminder(
        user_id=current_user.id,
        title=title,
        body=body,
        remind_at=remind_at_utc,
    )
    db.session.add(reminder)
    db.session.commit()

    flash("Reminder created.", "success")
    return redirect(url_for("reminders.index"))


@reminders_bp.route("/<int:reminder_id>/edit")
@login_required
def edit(reminder_id):
    reminder = get_reminder_or_404(reminder_id)
    if reminder.sent_at is not None:
        flash("Sent reminders cannot be edited.", "error")
        return redirect(url_for("reminders.index"))

    # Convert stored UTC remind_at back to user's local time for the form
    user_tz = ZoneInfo(current_user.time_zone or "UTC")
    local_dt = reminder.remind_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(user_tz)
    remind_at_local = local_dt.strftime("%Y-%m-%dT%H:%M")

    return render_template(
        "reminders/edit.html",
        reminder=reminder,
        remind_at_local=remind_at_local,
        tz_name=user_tz_name(current_user),
    )


@reminders_bp.route("/<int:reminder_id>/update", methods=["POST"])
@login_required
def update(reminder_id):
    reminder = get_reminder_or_404(reminder_id)
    if reminder.sent_at is not None:
        flash("Sent reminders cannot be edited.", "error")
        return redirect(url_for("reminders.index"))

    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip() or None
    dt_string = request.form.get("remind_at", "").strip()

    if not title:
        flash("Title is required.", "error")
        user_tz = ZoneInfo(current_user.time_zone or "UTC")
        local_dt = reminder.remind_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(user_tz)
        return render_template(
            "reminders/edit.html",
            reminder=reminder,
            remind_at_local=local_dt.strftime("%Y-%m-%dT%H:%M"),
            tz_name=user_tz_name(current_user),
            error=True,
        )

    remind_at_utc = parse_remind_at_from_user(dt_string, current_user)
    if remind_at_utc is None:
        flash("Please enter a valid date and time.", "error")
        user_tz = ZoneInfo(current_user.time_zone or "UTC")
        local_dt = reminder.remind_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(user_tz)
        return render_template(
            "reminders/edit.html",
            reminder=reminder,
            remind_at_local=local_dt.strftime("%Y-%m-%dT%H:%M"),
            tz_name=user_tz_name(current_user),
            error=True,
        )

    if remind_at_utc <= datetime.utcnow():
        flash("Reminder time must be in the future.", "error")
        user_tz = ZoneInfo(current_user.time_zone or "UTC")
        local_dt = reminder.remind_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(user_tz)
        return render_template(
            "reminders/edit.html",
            reminder=reminder,
            remind_at_local=local_dt.strftime("%Y-%m-%dT%H:%M"),
            tz_name=user_tz_name(current_user),
            error=True,
        )

    reminder.title = title
    reminder.body = body
    reminder.remind_at = remind_at_utc
    db.session.commit()

    flash("Reminder updated.", "success")
    return redirect(url_for("reminders.index"))


@reminders_bp.route("/<int:reminder_id>/delete", methods=["POST"])
@login_required
def delete(reminder_id):
    reminder = get_reminder_or_404(reminder_id)
    db.session.delete(reminder)
    db.session.commit()
    flash("Reminder deleted.", "success")
    return redirect(url_for("reminders.index"))


@reminders_bp.route("/<int:reminder_id>/duplicate", methods=["POST"])
@login_required
def duplicate(reminder_id):
    reminder = get_reminder_or_404(reminder_id)
    return redirect(url_for(
        "reminders.new",
        title=reminder.title,
        body=reminder.body or "",
    ))


@reminders_bp.route("/<int:reminder_id>/test", methods=["POST"])
@login_required
def test_send(reminder_id):
    reminder = get_reminder_or_404(reminder_id)

    if (current_user.credits or 0) < 1:
        flash("Not enough credits to send a test email.", "error")
        return redirect(url_for("reminders.index"))

    try:
        send_reminder_email(reminder)
        current_user.credits = (current_user.credits or 0) - 1
        db.session.commit()
        flash(
            f"Test email sent to {current_user.email}. "
            f"1 credit used ({current_user.credits} remaining).",
            "success",
        )
    except Exception as e:
        flash("Failed to send test email. Please try again.", "error")

    return redirect(url_for("reminders.index"))
