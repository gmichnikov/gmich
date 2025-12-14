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


@admin_bp.route("/view_logs")
@login_required
@admin_required
def view_logs():
    user_tz = pytz.timezone(current_user.time_zone)

    # Use outerjoin (LEFT JOIN) to include anonymous visits where actor_id is None
    log_entries = LogEntry.query.outerjoin(User, LogEntry.actor_id == User.id)
    log_entries = log_entries.order_by(LogEntry.timestamp.desc()).all()

    for log in log_entries:
        localized_timestamp = log.timestamp.replace(tzinfo=pytz.utc).astimezone(user_tz)
        tz_abbr = localized_timestamp.tzname()  # Gets the time zone abbreviation
        log.formatted_timestamp = (
            localized_timestamp.strftime("%Y-%m-%d, %I:%M:%S %p ") + tz_abbr
        )

    return render_template("admin/view_logs.html", log_entries=log_entries)


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
