import re
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlencode

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import User, LogEntry, db
from app.forms import AdminPasswordResetForm, AdminCreditForm
from functools import wraps
import pytz
from app.projects.better_signups.models import (
    SignupList,
    ListEditor,
    SwapRequest,
    SwapRequestTarget,
    SwapToken,
)

admin_bp = Blueprint("admin", __name__)

# LogEntry.project values that differ from registry project ids
LOG_PROJECT_DISPLAY_ALIASES = {
    "sports_admin": "Sports Schedule Admin",
}


def _log_project_display_name(project_id, registry_names):
    if project_id in LOG_PROJECT_DISPLAY_ALIASES:
        return LOG_PROJECT_DISPLAY_ALIASES[project_id]
    if project_id in registry_names:
        return registry_names[project_id]
    return project_id.replace("_", " ").title()


def get_log_project_filter_choices():
    """Project filter options for view_logs, sorted A–Z by display name."""
    from app.projects.registry import PROJECTS

    registry_names = {
        p["id"]: p["name"] for p in PROJECTS if p.get("type") == "project"
    }

    project_ids = set(registry_names)
    project_ids.update(["auth", "admin", *LOG_PROJECT_DISPLAY_ALIASES])

    for (project_id,) in db.session.query(LogEntry.project).distinct():
        if project_id:
            project_ids.add(project_id)

    choices = [
        (project_id, _log_project_display_name(project_id, registry_names))
        for project_id in project_ids
    ]
    choices.sort(key=lambda choice: choice[1].casefold())
    return choices


# Admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            if request.path.startswith("/sports-schedule-admin/api"):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Admin access required.",
                        }
                    ),
                    403,
                )
            flash("Admin access required.")
            return redirect(url_for("main.index"))
        return f(*args, **kwargs)

    return decorated_function


@admin_bp.route("/reset_password", methods=["GET", "POST"])
@login_required
@admin_required
def reset_password():
    form = AdminPasswordResetForm()
    form.email.choices = [(user.email, user.email) for user in User.query.all()]

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            user.set_password(form.new_password.data)
            db.session.commit()
            flash("Password reset successfully.")

            log_entry = LogEntry(
                project="admin",
                category="Reset Password",
                actor_id=current_user.id,
                description=f"{current_user.email} reset password of {user.email}",
            )
            db.session.add(log_entry)
            db.session.commit()
        else:
            flash("User not found.")

    return render_template("admin/reset_password.html", form=form)


@admin_bp.route("/add_credits", methods=["GET", "POST"])
@login_required
@admin_required
def add_credits():
    form = AdminCreditForm()
    form.email.choices = [
        (user.email, f"{user.email} ({user.credits} credits)")
        for user in User.query.order_by(User.email).all()
    ]

    if form.validate_on_submit():
        try:
            credits_to_add = int(form.credits.data)
            if credits_to_add <= 0:
                flash("Credits must be a positive number.", "error")
                return render_template("admin/add_credits.html", form=form)
        except ValueError:
            flash("Credits must be a valid number.", "error")
            return render_template("admin/add_credits.html", form=form)

        user = User.query.filter_by(email=form.email.data).first()
        if user:
            old_credits = user.credits
            user.credits += credits_to_add
            db.session.commit()

            flash(
                f"Successfully added {credits_to_add} credits to {user.email}. New balance: {user.credits}",
                "success",
            )

            log_entry = LogEntry(
                project="admin",
                category="Add Credits",
                actor_id=current_user.id,
                description=f"{current_user.email} added {credits_to_add} credits to {user.email} (from {old_credits} to {user.credits})",
            )
            db.session.add(log_entry)
            db.session.commit()
        else:
            flash("User not found.", "error")

    return render_template("admin/add_credits.html", form=form)


# Matches the description written by add_credits() above.
ADD_CREDITS_PATTERN = re.compile(r"added (\d+) credits to (\S+)")

# Mirrors User.credits' column default; every account starts here.
DEFAULT_STARTING_CREDITS = 10

RECENT_ACTIVITY_DAYS = 30

CREDIT_PROJECT_LABELS = {
    "adk_agent_demo": "ADK Agent Demo",
    "ask_many_llms": "Ask Many LLMs",
    "chatbot": "Greg-Bot",
    "daily_email": "Daily Email",
    "reminders": "Reminders",
    "sports_schedules": "Sports NL Query",
    "sports_schedules_digest": "Sports Digest",
}


def _new_credit_row():
    return {
        "added": 0,
        "by_project": defaultdict(int),
        "recent_by_project": defaultdict(int),
        "last_activity": None,
        "recent_events": 0,
        "total_events": 0,
        "no_credit_skips": 0,
        "failed_sends": 0,
    }


def get_credit_usage_by_user():
    """Per-user credit activity, derived rather than read from a ledger.

    Credits only ever increase through add_credits(), which writes an "Add
    Credits" LogEntry, and every account starts at DEFAULT_STARTING_CREDITS.
    That makes lifetime consumption recoverable from the current balance even
    though nothing records individual debits.

    The per-project breakdown is best effort and will undercount: reminder test
    sends and sports digest sends deduct a credit without leaving a per-event
    row, and Daily Email clamps balances at zero. Trust "consumed" over the sum
    of the project counts.
    """
    from app.projects.daily_email.models import DailyEmailSendLog
    from app.projects.reminders.models import Reminder
    from app.projects.sports_schedules.models import SportsScheduleScheduledDigest

    summary = defaultdict(_new_credit_row)
    cutoff = datetime.utcnow() - timedelta(days=RECENT_ACTIVITY_DAYS)

    def record(user_id, project, count, last_at, recent_count=0):
        if user_id is None:
            return
        row = summary[user_id]
        row["by_project"][project] += count
        row["total_events"] += count
        if recent_count:
            row["recent_by_project"][project] += recent_count
            row["recent_events"] += recent_count
        if last_at and (
            row["last_activity"] is None or last_at > row["last_activity"]
        ):
            row["last_activity"] = last_at

    # --- Credits granted by an admin, parsed back out of the log ---
    user_ids_by_email = {
        email.lower(): user_id
        for user_id, email in db.session.query(User.id, User.email)
        if email
    }
    for (description,) in db.session.query(LogEntry.description).filter(
        LogEntry.category == "Add Credits"
    ):
        match = ADD_CREDITS_PATTERN.search(description or "")
        if not match:
            continue
        user_id = user_ids_by_email.get(match.group(2).strip().lower())
        if user_id is not None:
            summary[user_id]["added"] += int(match.group(1))

    # --- Projects that log an explicit "Credit Usage" entry per deduction ---
    recent_logged = {
        (actor_id, project): count
        for actor_id, project, count in db.session.query(
            LogEntry.actor_id, LogEntry.project, func.count(LogEntry.id)
        )
        .filter(LogEntry.category == "Credit Usage", LogEntry.timestamp >= cutoff)
        .group_by(LogEntry.actor_id, LogEntry.project)
    }
    for actor_id, project, count, last_at in (
        db.session.query(
            LogEntry.actor_id,
            LogEntry.project,
            func.count(LogEntry.id),
            func.max(LogEntry.timestamp),
        )
        .filter(LogEntry.category == "Credit Usage")
        .group_by(LogEntry.actor_id, LogEntry.project)
    ):
        record(
            actor_id,
            project,
            count,
            last_at,
            recent_logged.get((actor_id, project), 0),
        )

    # --- Sports natural-language queries mark the credit inside the description ---
    nl_filters = (
        LogEntry.category == "NL Query",
        LogEntry.description.like("%1 credit used.%"),
    )
    recent_nl = dict(
        db.session.query(LogEntry.actor_id, func.count(LogEntry.id))
        .filter(*nl_filters, LogEntry.timestamp >= cutoff)
        .group_by(LogEntry.actor_id)
    )
    for actor_id, count, last_at in (
        db.session.query(
            LogEntry.actor_id, func.count(LogEntry.id), func.max(LogEntry.timestamp)
        )
        .filter(*nl_filters)
        .group_by(LogEntry.actor_id)
    ):
        record(
            actor_id, "sports_schedules", count, last_at, recent_nl.get(actor_id, 0)
        )

    # --- Daily Email keeps its own send log, including no-credit skips ---
    recent_email = dict(
        db.session.query(DailyEmailSendLog.user_id, func.count(DailyEmailSendLog.id))
        .filter(
            DailyEmailSendLog.status == "sent",
            DailyEmailSendLog.sent_at >= cutoff,
        )
        .group_by(DailyEmailSendLog.user_id)
    )
    for user_id, status, count, last_at in (
        db.session.query(
            DailyEmailSendLog.user_id,
            DailyEmailSendLog.status,
            func.count(DailyEmailSendLog.id),
            func.max(DailyEmailSendLog.sent_at),
        ).group_by(DailyEmailSendLog.user_id, DailyEmailSendLog.status)
    ):
        if user_id is None:
            continue
        if status == "sent":
            record(
                user_id,
                "daily_email",
                count,
                last_at,
                recent_email.get(user_id, 0),
            )
        elif status == "no_credits":
            summary[user_id]["no_credit_skips"] += count
        elif status == "failed":
            summary[user_id]["failed_sends"] += count

    # --- Reminders: one credit per row that actually went out ---
    recent_reminders = dict(
        db.session.query(Reminder.user_id, func.count(Reminder.id))
        .filter(Reminder.sent_at.isnot(None), Reminder.sent_at >= cutoff)
        .group_by(Reminder.user_id)
    )
    for user_id, count, last_at in (
        db.session.query(
            Reminder.user_id, func.count(Reminder.id), func.max(Reminder.sent_at)
        )
        .filter(Reminder.sent_at.isnot(None))
        .group_by(Reminder.user_id)
    ):
        record(
            user_id, "reminders", count, last_at, recent_reminders.get(user_id, 0)
        )

    # --- Sports digests only retain the most recent send, so count it as one ---
    for user_id, last_at in db.session.query(
        SportsScheduleScheduledDigest.user_id,
        SportsScheduleScheduledDigest.last_sent_at,
    ).filter(SportsScheduleScheduledDigest.last_sent_at.isnot(None)):
        record(
            user_id,
            "sports_schedules_digest",
            1,
            last_at,
            1 if last_at >= cutoff else 0,
        )

    return summary


def decorate_users_with_credits(users, user_tz):
    """Attach derived credit fields to each user for template rendering."""
    usage = get_credit_usage_by_user()

    for user in users:
        row = usage.get(user.id) or _new_credit_row()
        balance = user.credits or 0
        granted = DEFAULT_STARTING_CREDITS + row["added"]

        user.credit_added = row["added"]
        user.credit_granted = granted
        user.credit_consumed = max(0, granted - balance)
        user.credit_recent_events = row["recent_events"]
        user.credit_total_events = row["total_events"]
        user.credit_no_credit_skips = row["no_credit_skips"]
        user.credit_failed_sends = row["failed_sends"]
        user.credit_breakdown = sorted(
            (
                (CREDIT_PROJECT_LABELS.get(project, project), count,
                 row["recent_by_project"].get(project, 0))
                for project, count in row["by_project"].items()
                if count
            ),
            key=lambda item: -item[1],
        )

        last_at = row["last_activity"]
        user.credit_last_activity = last_at
        if last_at:
            localized = last_at.replace(tzinfo=pytz.utc).astimezone(user_tz)
            user.credit_last_activity_display = (
                localized.strftime("%Y-%m-%d, %I:%M %p ") + localized.tzname()
            )
            user.credit_days_since_activity = (datetime.utcnow() - last_at).days
        else:
            user.credit_last_activity_display = None
            user.credit_days_since_activity = None


@admin_bp.route("/users")
@login_required
@admin_required
def manage_users():
    """Admin view of all users with verification status and credit usage."""
    filter_status = request.args.get("filter", "all")
    sort_key = request.args.get("sort", "email")

    query = User.query

    if filter_status == "verified":
        query = query.filter_by(email_verified=True)
    elif filter_status == "unverified":
        query = query.filter_by(email_verified=False)
    elif filter_status == "out_of_credits":
        query = query.filter(User.credits <= 0)
    elif filter_status == "low_credits":
        query = query.filter(User.credits > 0, User.credits <= 5)

    users = query.order_by(User.email).all()

    user_tz = pytz.timezone(current_user.time_zone)
    decorate_users_with_credits(users, user_tz)

    if sort_key == "credits":
        users.sort(key=lambda u: (u.credits or 0, u.email))
    elif sort_key == "consumed":
        users.sort(key=lambda u: (-u.credit_consumed, u.email))
    elif sort_key == "recent":
        users.sort(key=lambda u: (-u.credit_recent_events, u.email))
    elif sort_key == "activity":
        users.sort(
            key=lambda u: (
                u.credit_last_activity is None,
                -(u.credit_last_activity.timestamp() if u.credit_last_activity else 0),
                u.email,
            )
        )

    totals = {
        "users": len(users),
        "consumed": sum(u.credit_consumed for u in users),
        "recent_events": sum(u.credit_recent_events for u in users),
        "out_of_credits": sum(1 for u in users if (u.credits or 0) <= 0),
        "low_credits": sum(1 for u in users if 0 < (u.credits or 0) <= 5),
        "no_credit_skips": sum(u.credit_no_credit_skips for u in users),
        "active_recently": sum(1 for u in users if u.credit_recent_events > 0),
    }

    return render_template(
        "admin/manage_users.html",
        users=users,
        filter_status=filter_status,
        sort_key=sort_key,
        totals=totals,
        recent_days=RECENT_ACTIVITY_DAYS,
    )


@admin_bp.route("/users/<int:user_id>/verify", methods=["POST"])
@login_required
@admin_required
def verify_user_email(user_id):
    """Manually verify a user's email address."""
    user = User.query.get_or_404(user_id)

    if user.email_verified:
        flash(f"{user.email} is already verified.", "info")
    else:
        # Manually verify the user
        user.email_verified = True
        user.verification_token = None
        user.verification_token_expiry = None
        db.session.commit()

        # Log the manual verification
        log_entry = LogEntry(
            project="admin",
            category="Manual Email Verification",
            actor_id=current_user.id,
            description=f"{current_user.email} manually verified email for {user.email}",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash(f"Successfully verified email for {user.email}.", "success")

    return redirect(url_for("admin.manage_users"))


def _query_log_entries(user_tz):
    """Run the log entry query from request args and return formatted entries."""
    project_filter = request.args.get("project", "")
    user_filter = request.args.get("user", "")
    search_filter = request.args.get("search", "")
    last_n_str = request.args.get("last_n", "50")
    last_n = None if last_n_str == "all" else int(last_n_str)

    query = LogEntry.query.outerjoin(User, LogEntry.actor_id == User.id)

    if project_filter:
        query = query.filter(LogEntry.project == project_filter)
    if user_filter:
        query = query.filter(User.email == user_filter)
    if search_filter:
        like_term = f"%{search_filter}%"
        query = query.filter(
            db.or_(LogEntry.category.ilike(like_term), LogEntry.description.ilike(like_term))
        )

    query = query.order_by(LogEntry.timestamp.desc())
    if last_n is not None:
        query = query.limit(last_n)

    log_entries = query.all()

    for log in log_entries:
        localized_timestamp = log.timestamp.replace(tzinfo=pytz.utc).astimezone(user_tz)
        tz_abbr = localized_timestamp.tzname()
        log.formatted_timestamp = (
            localized_timestamp.strftime("%Y-%m-%d, %I:%M:%S %p ") + tz_abbr
        )

    return log_entries


@admin_bp.route("/view_logs")
@login_required
@admin_required
def view_logs():
    user_tz = pytz.timezone(current_user.time_zone)
    log_entries = _query_log_entries(user_tz)

    all_users = (
        User.query.join(LogEntry, LogEntry.actor_id == User.id)
        .distinct()
        .order_by(User.email)
        .all()
    )

    return render_template(
        "admin/view_logs.html",
        log_entries=log_entries,
        all_users=all_users,
        project_choices=get_log_project_filter_choices(),
        selected_project=request.args.get("project", ""),
        selected_user=request.args.get("user", ""),
        search_value=request.args.get("search", ""),
        selected_last_n=request.args.get("last_n", "50"),
    )


@admin_bp.route("/view_logs/rows")
@login_required
@admin_required
def view_logs_rows():
    """Returns only the table row fragment for AJAX updates."""
    user_tz = pytz.timezone(current_user.time_zone)
    log_entries = _query_log_entries(user_tz)
    return render_template("admin/view_logs_rows.html", log_entries=log_entries)


@admin_bp.route("/view_all_signup_lists")
@login_required
@admin_required
def view_all_signup_lists():
    """Admin view of all signup lists in the Better Signups project."""
    from app.projects.better_signups.models import Event, Item

    # Get all lists ordered by creation date (newest first)
    lists = SignupList.query.order_by(SignupList.created_at.desc()).all()

    # For each list, get all editors (creator + additional editors) and calculate spots
    for signup_list in lists:
        # Get additional editors (excluding creator)
        additional_editors = ListEditor.query.filter_by(list_id=signup_list.id).all()
        # Combine creator with additional editors for display
        all_editors = [signup_list.creator]
        for editor in additional_editors:
            if editor.user:
                all_editors.append(editor.user)
        signup_list.all_editors = all_editors
        # Also get pending editor emails (editors without user accounts)
        signup_list.pending_editor_emails = [
            editor.email
            for editor in additional_editors
            if not editor.user and editor.email
        ]

        # Calculate total spots (taken and available)
        total_spots_taken = 0
        total_spots_available = 0
        if signup_list.list_type == "events":
            for event in signup_list.events:
                total_spots_taken += event.get_spots_taken()
                total_spots_available += event.spots_available
        else:  # items
            for item in signup_list.items:
                total_spots_taken += item.get_spots_taken()
                total_spots_available += item.spots_available

        signup_list.total_spots_taken = total_spots_taken
        signup_list.total_spots_available = total_spots_available

    return render_template("admin/view_all_signup_lists.html", lists=lists)


@admin_bp.route("/swap_requests")
@login_required
@admin_required
def view_swap_requests():
    """View all swap requests in the system"""
    from sqlalchemy.orm import joinedload

    # Get all swap requests with eager loading
    swap_requests = (
        SwapRequest.query.options(
            joinedload(SwapRequest.requestor_signup),
            joinedload(SwapRequest.requestor_family_member),
            joinedload(SwapRequest.list),
            joinedload(SwapRequest.targets),
            joinedload(SwapRequest.tokens),
        )
        .order_by(SwapRequest.created_at.desc())
        .all()
    )

    # Enhance swap requests with additional info
    for sr in swap_requests:
        # Get requestor's element description
        requestor_signup = sr.requestor_signup
        
        # If signup still exists (might be None if deleted/completed)
        if requestor_signup:
            if requestor_signup.event_id:
                from app.projects.better_signups.models import Event

                event = Event.query.get(requestor_signup.event_id)
                if event:
                    if event.event_type == "date":
                        sr.requestor_element_desc = event.event_date.strftime("%B %d, %Y")
                    else:
                        sr.requestor_element_desc = event.event_datetime.strftime(
                            "%B %d, %Y at %I:%M %p"
                        )
                else:
                    sr.requestor_element_desc = "[Deleted Event]"
            else:
                from app.projects.better_signups.models import Item

                item = Item.query.get(requestor_signup.item_id)
                if item:
                    sr.requestor_element_desc = item.name
                else:
                    sr.requestor_element_desc = "[Deleted Item]"
        else:
            # Signup no longer exists (completed swap or deleted)
            sr.requestor_element_desc = "[Signup Deleted]"

        # Get target elements descriptions
        sr.target_descriptions = []
        for target in sr.targets:
            if target.target_element_type == "event":
                from app.projects.better_signups.models import Event

                event = Event.query.get(target.target_element_id)
                if event:
                    if event.event_type == "date":
                        sr.target_descriptions.append(
                            event.event_date.strftime("%B %d, %Y")
                        )
                    else:
                        sr.target_descriptions.append(
                            event.event_datetime.strftime("%B %d, %Y at %I:%M %p")
                        )
                else:
                    sr.target_descriptions.append("[Deleted Event]")
            else:
                from app.projects.better_signups.models import Item

                item = Item.query.get(target.target_element_id)
                if item:
                    sr.target_descriptions.append(item.name)
                else:
                    sr.target_descriptions.append("[Deleted Item]")

        # Count tokens
        sr.token_count = len(sr.tokens)

    return render_template("admin/view_swap_requests.html", swap_requests=swap_requests)


@admin_bp.route("/swap_requests/<int:swap_request_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_swap_request(swap_request_id):
    """Delete a swap request and all associated tokens"""
    swap_request = SwapRequest.query.get_or_404(swap_request_id)

    # Get info for logging before deletion
    requestor_family_member_name = swap_request.requestor_family_member.display_name
    list_name = swap_request.list.name

    # Delete swap request (cascade will delete targets and tokens)
    db.session.delete(swap_request)

    # Log the action
    log_entry = LogEntry(
        project="admin",
        category="Delete Swap Request",
        actor_id=current_user.id,
        description=f"{current_user.email} deleted swap request for {requestor_family_member_name} in list '{list_name}' (ID: {swap_request_id})",
    )
    db.session.add(log_entry)

    try:
        db.session.commit()
        flash(f"Swap request deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting swap request: {str(e)}", "error")

    return redirect(url_for("admin.view_swap_requests"))


# --- Travel Log Tags (global tags, admin CRUD) ---


@admin_bp.route("/travel-log-tags")
@login_required
@admin_required
def travel_log_tags():
    """List and manage global Travel Log tags."""
    from app.projects.travel_log.models import TlogTag

    tags = TlogTag.query.filter_by(scope="global").order_by(TlogTag.name).all()
    return render_template("admin/travel_log_tags.html", tags=tags)


@admin_bp.route("/travel-log-tags/create", methods=["POST"])
@login_required
@admin_required
def travel_log_tags_create():
    """Create a new global tag."""
    from app.projects.travel_log.models import TlogTag
    from app.projects.travel_log.utils import normalize_tag_name, normalize_hex_color

    raw = (request.form.get("name") or "").strip()
    name = normalize_tag_name(raw)
    if not name:
        flash("Invalid tag name. Use lowercase letters, numbers, and hyphens only (e.g. kid-friendly).", "error")
        return redirect(url_for("admin.travel_log_tags"))

    existing = TlogTag.query.filter_by(scope="global", name=name).first()
    if existing:
        flash(f'Tag "{name}" already exists.', "error")
        return redirect(url_for("admin.travel_log_tags"))

    bg_color = normalize_hex_color(request.form.get("bg_color") or "")

    tag = TlogTag(name=name, scope="global", user_id=None, collection_id=None, bg_color=bg_color)
    db.session.add(tag)
    log_entry = LogEntry(
        project="admin",
        category="Travel Log Tags",
        actor_id=current_user.id,
        description=f"{current_user.email} created tag '{name}'",
    )
    db.session.add(log_entry)
    db.session.commit()
    flash(f'Tag "{name}" created.', "success")
    return redirect(url_for("admin.travel_log_tags"))


@admin_bp.route("/travel-log-tags/<int:tag_id>/update", methods=["POST"])
@login_required
@admin_required
def travel_log_tags_update(tag_id):
    """Update a global tag (name, bg_color)."""
    from app.projects.travel_log.models import TlogTag
    from app.projects.travel_log.utils import normalize_tag_name, normalize_hex_color

    tag = TlogTag.query.filter_by(id=tag_id, scope="global").first_or_404()
    raw = (request.form.get("name") or "").strip()
    name = normalize_tag_name(raw)
    if not name:
        flash("Invalid tag name. Use lowercase letters, numbers, and hyphens only.", "error")
        return redirect(url_for("admin.travel_log_tags"))

    bg_color = normalize_hex_color(request.form.get("bg_color") or "")
    tag.bg_color = bg_color if bg_color else None

    if name != tag.name:
        existing = TlogTag.query.filter_by(scope="global", name=name).first()
        if existing:
            flash(f'Tag "{name}" already exists.', "error")
            return redirect(url_for("admin.travel_log_tags"))
        old_name = tag.name
        tag.name = name
        log_entry = LogEntry(
            project="admin",
            category="Travel Log Tags",
            actor_id=current_user.id,
            description=f"{current_user.email} renamed tag '{old_name}' to '{name}'",
        )
        db.session.add(log_entry)
    db.session.commit()
    flash("Tag updated.", "success")
    return redirect(url_for("admin.travel_log_tags"))


@admin_bp.route("/travel-log-tags/<int:tag_id>/delete", methods=["POST"])
@login_required
@admin_required
def travel_log_tags_delete(tag_id):
    """Delete a global tag (removes from all entries)."""
    from app.projects.travel_log.models import TlogTag

    tag = TlogTag.query.filter_by(id=tag_id, scope="global").first_or_404()
    name = tag.name
    entry_count = tag.entries.count()
    db.session.delete(tag)
    log_entry = LogEntry(
        project="admin",
        category="Travel Log Tags",
        actor_id=current_user.id,
        description=f"{current_user.email} deleted tag '{name}' (was on {entry_count} entries)",
    )
    db.session.add(log_entry)
    db.session.commit()
    flash(f'Tag "{name}" deleted.', "success")
    return redirect(url_for("admin.travel_log_tags"))


# ---------------------------------------------------------------------------
# Helper — Admin hub
# ---------------------------------------------------------------------------

@admin_bp.route("/helper")
@login_required
@admin_required
def helper_admin():
    return render_template("admin/helper_admin.html")


# ---------------------------------------------------------------------------
# Helper — Group management
# ---------------------------------------------------------------------------

@admin_bp.route("/helper/groups")
@login_required
@admin_required
def helper_groups():
    from app.projects.helper.models import HelperGroup
    groups = HelperGroup.query.order_by(HelperGroup.created_at.desc()).all()
    return render_template("admin/helper_groups.html", groups=groups)


@admin_bp.route("/helper/groups/new", methods=["GET", "POST"])
@login_required
@admin_required
def helper_group_new():
    from app.projects.helper.models import HelperGroup, HelperGroupMember

    if request.method == "GET":
        return render_template("admin/helper_group_new.html")

    # --- Parse form ---
    name = request.form.get("name", "").strip()
    inbound_email_prefix = request.form.get("inbound_email_prefix", "").strip().lower()
    inbound_email = f"{inbound_email_prefix}@helper.gregmichnikov.com" if inbound_email_prefix else ""
    member_emails_raw = request.form.get("member_emails", "")
    member_emails = [e.strip().lower() for e in member_emails_raw.splitlines() if e.strip()]

    errors = []

    if not name:
        errors.append("Group name is required.")
    if not inbound_email_prefix:
        errors.append("Inbound email prefix is required.")
    if not member_emails:
        errors.append("At least one member email is required.")

    # Check inbound_email uniqueness
    if inbound_email and HelperGroup.query.filter_by(inbound_email=inbound_email).first():
        errors.append(f"Inbound email '{inbound_email}' is already in use by another group.")

    # Resolve all member emails to Users
    resolved_users = []
    bad_emails = []
    for email in member_emails:
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user:
            resolved_users.append(user)
        else:
            bad_emails.append(email)

    if bad_emails:
        errors.append(f"These emails don't match any existing user: {', '.join(bad_emails)}")

    if errors:
        return render_template(
            "admin/helper_group_new.html",
            errors=errors,
            name=name,
            inbound_email_prefix=inbound_email_prefix,
            member_emails=member_emails_raw,
        )

    # --- Atomic create ---
    try:
        group = HelperGroup(
            name=name,
            inbound_email=inbound_email,
            created_by_user_id=current_user.id,
        )
        db.session.add(group)
        db.session.flush()

        seen_user_ids = set()
        for user in resolved_users:
            if user.id not in seen_user_ids:
                db.session.add(HelperGroupMember(group_id=group.id, user_id=user.id))
                seen_user_ids.add(user.id)

        db.session.commit()
        flash(f"Group '{name}' created with {len(seen_user_ids)} member(s).", "success")
        return redirect(url_for("admin.helper_groups"))
    except Exception as e:
        db.session.rollback()
        return render_template(
            "admin/helper_group_new.html",
            errors=[f"Unexpected error: {e}"],
            name=name,
            inbound_email_prefix=inbound_email_prefix,
            member_emails=member_emails_raw,
        )


@admin_bp.route("/helper/groups/<int:group_id>/add-member", methods=["POST"])
@login_required
@admin_required
def helper_group_add_member(group_id):
    from app.projects.helper.models import HelperGroup, HelperGroupMember

    group = HelperGroup.query.get_or_404(group_id)
    email = request.form.get("email", "").strip().lower()

    if not email:
        flash("Email is required.", "error")
        return redirect(url_for("admin.helper_groups"))

    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user:
        flash(f"No user found with email '{email}'.", "error")
        return redirect(url_for("admin.helper_groups"))

    existing = HelperGroupMember.query.filter_by(group_id=group.id, user_id=user.id).first()
    if existing:
        flash(f"{email} is already a member of '{group.name}'.", "error")
        return redirect(url_for("admin.helper_groups"))

    db.session.add(HelperGroupMember(group_id=group.id, user_id=user.id))
    db.session.commit()
    flash(f"Added {email} to '{group.name}'.", "success")
    return redirect(url_for("admin.helper_groups"))


@admin_bp.route("/helper/action-log")
@login_required
@admin_required
def helper_action_log():
    from app.projects.helper.models import HelperActionLog
    page = request.args.get("page", 1, type=int)
    rows = (
        HelperActionLog.query
        .order_by(HelperActionLog.created_at.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )
    return render_template("admin/helper_action_log.html", rows=rows)


@admin_bp.route("/helper/evals")
@login_required
@admin_required
def helper_evals():
    """Router eval run history."""
    from app.projects.helper.models import HelperEvalRun
    page = request.args.get("page", 1, type=int)
    runs = (
        HelperEvalRun.query
        .order_by(HelperEvalRun.run_at.desc())
        .paginate(page=page, per_page=30, error_out=False)
    )
    return render_template("admin/helper_evals.html", runs=runs)


@admin_bp.route("/helper/evals/<int:run_id>")
@login_required
@admin_required
def helper_eval_run(run_id):
    """Detail view for a single eval run."""
    import json
    import os
    from app.projects.helper.models import HelperEvalRun
    run = HelperEvalRun.query.get_or_404(run_id)

    # Load fixture context (active + retired) keyed by fixture_id
    fixture_context = {}
    fixture_file = os.path.join(
        os.path.dirname(__file__), "..", "projects", "helper", "evals", "router_fixtures.json"
    )
    try:
        with open(os.path.abspath(fixture_file)) as f:
            data = json.load(f)
        all_fixtures = []
        if isinstance(data, list):
            all_fixtures = data
        else:
            all_fixtures = data.get("fixtures", []) + data.get("retired", [])
        fixture_context = {fx["id"]: fx for fx in all_fixtures}
    except Exception:
        pass

    return render_template("admin/helper_eval_run.html", run=run, fixture_context=fixture_context)


@admin_bp.route("/helper/email-detail")
@login_required
@admin_required
def helper_email_detail():
    from app.projects.helper.models import HelperInboundEmail
    page = request.args.get("page", 1, type=int)
    rows = (
        HelperInboundEmail.query
        .order_by(HelperInboundEmail.created_at.desc())
        .paginate(page=page, per_page=25, error_out=False)
    )
    return render_template("admin/helper_email_detail.html", rows=rows)


# ---------------------------------------------------------------------------
# Helper — Task audit (core unit: one row per task)
# ---------------------------------------------------------------------------


@admin_bp.route("/helper/tasks")
@login_required
@admin_required
def helper_tasks():
    """Paginated task list for admin audit (reminders, provenance, people)."""
    from sqlalchemy.orm import joinedload

    from app.projects.helper.models import HelperGroup, HelperTask

    page = request.args.get("page", 1, type=int)
    status = (request.args.get("status") or "").strip().lower()
    group_id = request.args.get("group_id", type=int)

    q = HelperTask.query.options(
        joinedload(HelperTask.group),
        joinedload(HelperTask.assignee),
        joinedload(HelperTask.creator),
    )
    if status in ("open", "complete"):
        q = q.filter(HelperTask.status == status)
    if group_id:
        q = q.filter(HelperTask.group_id == group_id)

    rows = q.order_by(HelperTask.updated_at.desc()).paginate(
        page=page, per_page=40, error_out=False
    )
    groups = HelperGroup.query.order_by(HelperGroup.name).all()

    def _tasks_page_url(p: int) -> str:
        args = {"page": p}
        if status in ("open", "complete"):
            args["status"] = status
        if group_id:
            args["group_id"] = group_id
        return url_for("admin.helper_tasks") + "?" + urlencode(args)

    prev_url = _tasks_page_url(rows.prev_num) if rows.has_prev else None
    next_url = _tasks_page_url(rows.next_num) if rows.has_next else None

    return render_template(
        "admin/helper_tasks.html",
        rows=rows,
        groups=groups,
        filter_status=status,
        filter_group_id=group_id,
        prev_url=prev_url,
        next_url=next_url,
    )


@admin_bp.route("/helper/tasks/<int:task_id>")
@login_required
@admin_required
def helper_task_detail(task_id):
    """Single-task audit: fields, reminders, inbound provenance, action logs."""
    from sqlalchemy.orm import joinedload

    from app.projects.helper.models import HelperActionLog, HelperTask

    task = (
        HelperTask.query.options(
            joinedload(HelperTask.group),
            joinedload(HelperTask.assignee),
            joinedload(HelperTask.creator),
            joinedload(HelperTask.completer),
            joinedload(HelperTask.source_inbound_email),
            joinedload(HelperTask.completed_via_inbound_email),
            joinedload(HelperTask.reminder_logs),
        )
        .filter_by(id=task_id)
        .first_or_404()
    )

    reminder_logs = sorted(
        task.reminder_logs or [],
        key=lambda r: r.created_at,
    )

    source_actions = []
    if task.source_inbound_email_id:
        source_actions = (
            HelperActionLog.query.filter_by(
                inbound_email_id=task.source_inbound_email_id
            )
            .order_by(HelperActionLog.created_at.asc())
            .limit(80)
            .all()
        )

    completion_actions = []
    cid = task.completed_via_inbound_email_id
    if cid and cid != task.source_inbound_email_id:
        completion_actions = (
            HelperActionLog.query.filter_by(inbound_email_id=cid)
            .order_by(HelperActionLog.created_at.asc())
            .limit(80)
            .all()
        )

    return render_template(
        "admin/helper_task_detail.html",
        task=task,
        reminder_logs=reminder_logs,
        source_actions=source_actions,
        completion_actions=completion_actions,
    )
