from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
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


# Admin decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
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


@admin_bp.route("/users")
@login_required
@admin_required
def manage_users():
    """Admin view of all users with verification status."""
    # Get filter parameter
    filter_status = request.args.get("filter", "all")  # 'all', 'verified', 'unverified'

    # Query users
    query = User.query

    if filter_status == "verified":
        query = query.filter_by(email_verified=True)
    elif filter_status == "unverified":
        query = query.filter_by(email_verified=False)

    users = query.order_by(User.email).all()

    return render_template(
        "admin/manage_users.html", users=users, filter_status=filter_status
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


@admin_bp.route("/helper/inbound-log")
@login_required
@admin_required
def helper_inbound_log():
    from app.projects.helper.models import HelperInboundEmail
    page = request.args.get("page", 1, type=int)
    rows = (
        HelperInboundEmail.query
        .order_by(HelperInboundEmail.created_at.desc())
        .paginate(page=page, per_page=50, error_out=False)
    )
    return render_template("admin/helper_inbound_log.html", rows=rows)


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
