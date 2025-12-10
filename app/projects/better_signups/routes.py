"""
Better Signups - Routes
Handles signup list creation, management, and signups
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from datetime import datetime, date
from app import db
from app.forms import (
    FamilyMemberForm,
    CreateSignupListForm,
    EditSignupListForm,
    AddListEditorForm,
    EventForm,
)
from app.projects.better_signups.models import (
    FamilyMember,
    SignupList,
    ListEditor,
    Event,
)
from app.models import User
import pytz

bp = Blueprint(
    "better_signups",
    __name__,
    url_prefix="/better-signups",
    template_folder="templates",
    static_folder="static",
)


@bp.route("/")
@login_required
def index():
    """Main Better Signups page"""
    # Get lists created by current user
    my_lists = (
        SignupList.query.filter_by(creator_id=current_user.id)
        .order_by(SignupList.created_at.desc())
        .all()
    )

    # Get lists where user is an editor (but not creator)
    # This includes lists where user_id matches, or email matches (for pending invitations)
    editor_lists = (
        SignupList.query.join(ListEditor)
        .filter(
            SignupList.creator_id != current_user.id,
            or_(
                ListEditor.user_id == current_user.id,
                ListEditor.email == current_user.email.lower(),
            ),
        )
        .order_by(SignupList.created_at.desc())
        .all()
    )

    return render_template(
        "better_signups/index.html", my_lists=my_lists, editor_lists=editor_lists
    )


@bp.route("/family-members")
@login_required
def family_members():
    """View and manage family members"""
    # Ensure "self" family member exists
    from app.projects.better_signups.utils import ensure_self_family_member

    ensure_self_family_member(current_user)
    
    form = FamilyMemberForm()
    family_members_list = (
        FamilyMember.query.filter_by(user_id=current_user.id)
        .order_by(FamilyMember.is_self.desc(), FamilyMember.created_at)
        .all()
    )
    
    return render_template(
        "better_signups/family_members.html",
        form=form,
        family_members=family_members_list,
    )


@bp.route("/family-members/add", methods=["POST"])
@login_required
def add_family_member():
    """Add a new family member"""
    form = FamilyMemberForm()
    
    if form.validate_on_submit():
        # Check if user already has a "self" family member
        # (This shouldn't happen if auto-creation works, but just in case)
        existing_self = FamilyMember.query.filter_by(
            user_id=current_user.id, is_self=True
        ).first()
        
        if not existing_self:
            # Create "self" family member if it doesn't exist
            self_member = FamilyMember(
                user_id=current_user.id,
                display_name=current_user.full_name,
                is_self=True,
            )
            db.session.add(self_member)
        
        # Create new family member
        family_member = FamilyMember(
            user_id=current_user.id,
            display_name=form.display_name.data.strip(),
            is_self=False,
        )
        db.session.add(family_member)
        db.session.commit()
        
        flash(
            f'Family member "{family_member.display_name}" added successfully.',
            "success",
        )
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")
    
    return redirect(url_for("better_signups.family_members"))


@bp.route("/family-members/<int:member_id>/delete", methods=["POST"])
@login_required
def delete_family_member(member_id):
    """Delete a family member"""
    family_member = FamilyMember.query.get_or_404(member_id)
    
    # Verify the family member belongs to the current user
    if family_member.user_id != current_user.id:
        flash("You do not have permission to delete this family member.", "error")
        return redirect(url_for("better_signups.family_members"))
    
    # Prevent deletion of "self" family member
    if family_member.is_self:
        flash("You cannot delete your own family member record.", "error")
        return redirect(url_for("better_signups.family_members"))
    
    # Check if there are any active signups for this family member
    active_signups = [s for s in family_member.signups if s.cancelled_at is None]
    if active_signups:
        flash(
            f'Cannot delete "{family_member.display_name}" because they have active signups. '
            "Please cancel all signups first.",
            "error",
        )
        return redirect(url_for("better_signups.family_members"))
    
    name = family_member.display_name
    db.session.delete(family_member)
    db.session.commit()
    
    flash(f'Family member "{name}" deleted successfully.', "success")
    return redirect(url_for("better_signups.family_members"))


@bp.route("/lists/create", methods=["GET", "POST"])
@login_required
def create_list():
    """Create a new signup list"""
    form = CreateSignupListForm()
    
    if form.validate_on_submit():
        # Create new list
        new_list = SignupList(
            name=form.name.data.strip(),
            description=(
                form.description.data.strip() if form.description.data else None
            ),
            list_type=form.list_type.data,
            creator_id=current_user.id,
            accepting_signups=True,
        )
        
        # Generate UUID
        new_list.generate_uuid()
        
        # Set password if provided
        if form.list_password.data and form.list_password.data.strip():
            new_list.set_list_password(form.list_password.data)
        
        db.session.add(new_list)
        db.session.commit()
        
        flash(f'List "{new_list.name}" created successfully!', "success")
        return redirect(url_for("better_signups.view_list", uuid=new_list.uuid))
    
    return render_template("better_signups/create_list.html", form=form)


@bp.route("/lists/<string:uuid>")
@login_required
def view_list(uuid):
    """View and edit a signup list (editor view)"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    
    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to view this list.", "error")
        return redirect(url_for("better_signups.index"))
    
    form = EditSignupListForm(obj=signup_list)
    form.accepting_signups.data = signup_list.accepting_signups
    
    # Form for adding editors (only shown to creator)
    add_editor_form = (
        AddListEditorForm() if signup_list.creator_id == current_user.id else None
    )

    # Get list of editors (excluding creator)
    editors = ListEditor.query.filter_by(list_id=signup_list.id).all()

    # Get events if this is an events list
    events = (
        Event.query.filter_by(list_id=signup_list.id)
        .order_by(
            Event.event_date.asc().nullslast(), Event.event_datetime.asc().nullslast()
        )
        .all()
        if signup_list.list_type == "events"
        else []
    )

    return render_template(
        "better_signups/view_list.html",
        list=signup_list,
        form=form,
        add_editor_form=add_editor_form,
        editors=editors,
        events=events,
    )


@bp.route("/lists/<string:uuid>/edit", methods=["POST"])
@login_required
def edit_list(uuid):
    """Edit a signup list"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    
    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to edit this list.", "error")
        return redirect(url_for("better_signups.index"))
    
    form = EditSignupListForm()
    
    if form.validate_on_submit():
        signup_list.name = form.name.data.strip()
        signup_list.description = (
            form.description.data.strip() if form.description.data else None
        )
        signup_list.accepting_signups = form.accepting_signups.data
        
        # Update password if provided
        if form.list_password.data and form.list_password.data.strip():
            signup_list.set_list_password(form.list_password.data)
        
        db.session.commit()
        
        flash(f'List "{signup_list.name}" updated successfully!', "success")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))


@bp.route("/lists/<string:uuid>/delete", methods=["POST"])
@login_required
def delete_list(uuid):
    """Delete a signup list"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    
    # Only creator can delete
    if signup_list.creator_id != current_user.id:
        flash("Only the list creator can delete this list.", "error")
        return redirect(url_for("better_signups.index"))
    
    # Check if there are any signups
    from app.projects.better_signups.models import Signup, Event, Item

    event_ids = [e.id for e in signup_list.events]
    item_ids = [i.id for i in signup_list.items]
    
    has_signups = False
    if event_ids:
        has_signups = (
            db.session.query(Signup).filter(Signup.event_id.in_(event_ids)).first()
            is not None
        )
    if not has_signups and item_ids:
        has_signups = (
            db.session.query(Signup).filter(Signup.item_id.in_(item_ids)).first()
            is not None
        )
    
    if has_signups:
        flash(
            "Cannot delete a list that has signups. Please remove all signups first.",
            "error",
        )
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))
    
    name = signup_list.name
    db.session.delete(signup_list)
    db.session.commit()
    
    flash(f'List "{name}" deleted successfully.', "success")
    return redirect(url_for("better_signups.index"))


@bp.route("/lists/<string:uuid>/editors/add", methods=["POST"])
@login_required
def add_editor(uuid):
    """Add an editor to a signup list"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()

    # Only creator can add editors
    if signup_list.creator_id != current_user.id:
        flash("Only the list creator can add editors.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    form = AddListEditorForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        # Try to find user by email
        user = User.query.filter_by(email=email).first()

        # Check if user is already an editor (or is the creator)
        if user and user.id == signup_list.creator_id:
            flash("The list creator is already an editor.", "error")
            return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

        # Check if already an editor (by user_id or by email)
        existing_editor = None
        if user:
            existing_editor = ListEditor.query.filter_by(
                list_id=signup_list.id, user_id=user.id
            ).first()
        else:
            existing_editor = ListEditor.query.filter_by(
                list_id=signup_list.id, email=email
            ).first()

        if existing_editor:
            flash("This email is already an editor.", "error")
            return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

        # Add as editor (with user_id if user exists, otherwise just email)
        editor = ListEditor(
            list_id=signup_list.id, user_id=user.id if user else None, email=email
        )
        db.session.add(editor)
        db.session.commit()

        # Generic success message to avoid email enumeration
        flash(f"Editor added successfully. {email} can now edit this list.", "success")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")

    return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))


@bp.route("/lists/<string:uuid>/editors/<int:editor_id>/remove", methods=["POST"])
@login_required
def remove_editor(uuid, editor_id):
    """Remove an editor from a signup list"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()

    # Only creator can remove editors
    if signup_list.creator_id != current_user.id:
        flash("Only the list creator can remove editors.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    editor = ListEditor.query.get_or_404(editor_id)

    # Verify the editor belongs to this list
    if editor.list_id != signup_list.id:
        flash("Invalid editor.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    # Get editor info before deletion
    editor_email = editor.get_display_email() or "Unknown"

    db.session.delete(editor)
    db.session.commit()

    # Generic message to avoid revealing whether user has an account
    flash(f"Editor {editor_email} removed successfully.", "success")
    return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))


@bp.route("/lists/<string:uuid>/events/add", methods=["GET", "POST"])
@login_required
def add_event(uuid):
    """Add an event to a signup list"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()

    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to add events to this list.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    # Only allow events in events-type lists
    if signup_list.list_type != "events":
        flash("This list is not configured for events.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    form = EventForm()

    # Set default timezone to creator's timezone
    form.timezone.data = signup_list.creator.time_zone

    # Check if list already has events and enforce consistent event type
    existing_events = Event.query.filter_by(list_id=signup_list.id).all()
    existing_type = None
    if existing_events:
        # All events must use the same type
        existing_type = existing_events[0].event_type
        form.event_type.data = existing_type
        form.event_type.render_kw = {"disabled": True}  # Disable the field

    if form.validate_on_submit():
        # Use existing type if list already has events (in case form was tampered with)
        if existing_events and existing_type:
            form.event_type.data = existing_type

        # Double-check event type consistency
        if existing_events and form.event_type.data != existing_type:
            flash(
                f'All events in this list must use the same type. This list uses "{existing_type}" events.',
                "error",
            )
            return render_template(
                "better_signups/event_form.html",
                form=form,
                list=signup_list,
                event=None,
            )
        event = Event(
            list_id=signup_list.id,
            event_type=form.event_type.data,
            location=form.location.data.strip() if form.location.data else None,
            location_is_link=form.location_is_link.data,
            description=(
                form.description.data.strip() if form.description.data else None
            ),
            spots_available=form.spots_available.data,
        )

        if form.event_type.data == "date":
            event.event_date = form.event_date.data
            event.event_datetime = None
            event.timezone = None
            event.duration_minutes = None
        else:  # datetime
            # Parse datetime string (format: YYYY-MM-DD HH:MM or YYYY-MM-DDTHH:MM from datetime-local)
            datetime_str = form.event_datetime.data.strip()
            # Handle both formats: YYYY-MM-DD HH:MM and YYYY-MM-DDTHH:MM
            datetime_str = datetime_str.replace("T", " ")
            try:
                event_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                event.event_datetime = event_datetime
                event.event_date = None
                # Use selected timezone from form
                event.timezone = form.timezone.data if form.timezone.data else signup_list.creator.time_zone
                # Handle duration_minutes - can be None (optional) or an integer
                if (
                    form.duration_minutes.data is not None
                    and form.duration_minutes.data != ""
                ):
                    event.duration_minutes = int(form.duration_minutes.data)
                else:
                    event.duration_minutes = None
            except ValueError:
                flash(
                    "Invalid date/time format. Please use YYYY-MM-DD HH:MM format.",
                    "error",
                )
                return render_template(
                    "better_signups/event_form.html",
                    form=form,
                    list=signup_list,
                    event=None,
                )

        db.session.add(event)
        db.session.commit()

        flash(f"Event added successfully!", "success")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))
    else:
        # Show form errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "error")

    return render_template(
        "better_signups/event_form.html", form=form, list=signup_list, event=None
    )


@bp.route("/lists/<string:uuid>/events/<int:event_id>/edit", methods=["GET", "POST"])
@login_required
def edit_event(uuid, event_id):
    """Edit an event"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    event = Event.query.get_or_404(event_id)

    # Verify event belongs to this list
    if event.list_id != signup_list.id:
        flash("Invalid event.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to edit this event.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    # Only populate from event object on GET request, not on POST
    if request.method == "GET":
        form = EventForm(obj=event)

        # Check if list has other events and enforce consistent event type
        other_events = Event.query.filter(
            Event.list_id == signup_list.id, Event.id != event.id
        ).all()
        if other_events:
            # All events must use the same type
            existing_type = other_events[0].event_type
            if form.event_type.data != existing_type:
                form.event_type.data = existing_type
            form.event_type.render_kw = {"disabled": True}  # Disable the field

        # Populate form with existing data
        if event.event_type == "date":
            form.event_date.data = event.event_date
        else:
            if event.event_datetime:
                # Format for datetime-local input (YYYY-MM-DDTHH:MM)
                form.event_datetime.data = event.event_datetime.strftime(
                    "%Y-%m-%dT%H:%M"
                )
            form.timezone.data = event.timezone if event.timezone else signup_list.creator.time_zone
            form.duration_minutes.data = event.duration_minutes
            form.location_is_link.data = event.location_is_link
    else:
        # POST request - use submitted form data
        form = EventForm()
        # Set default timezone for POST as well if not provided
        if not form.timezone.data:
            form.timezone.data = signup_list.creator.time_zone

        # Check if list has other events and enforce consistent event type
        other_events = Event.query.filter(
            Event.list_id == signup_list.id, Event.id != event.id
        ).all()
        if other_events:
            # All events must use the same type
            existing_type = other_events[0].event_type
            form.event_type.render_kw = {"disabled": True}  # Disable the field
            # If event type was disabled, use the existing type from hidden input
            # or fall back to the event's current type
            if not form.event_type.data:
                form.event_type.data = event.event_type

    if form.validate_on_submit():
        # Check if reducing spots below current signups
        current_signups = event.get_spots_taken()
        if form.spots_available.data < current_signups:
            flash(
                f"Cannot reduce spots below {current_signups} (current signups).",
                "error",
            )
            return render_template(
                "better_signups/event_form.html",
                form=form,
                list=signup_list,
                event=event,
            )

        # Update common fields
        event.location = form.location.data.strip() if form.location.data else None
        event.location_is_link = form.location_is_link.data
        event.description = (
            form.description.data.strip() if form.description.data else None
        )
        event.spots_available = form.spots_available.data

        # Use the event's existing type, not form data (don't allow type changes on edit)
        if event.event_type == "date":
            event.event_date = form.event_date.data
            event.event_datetime = None
            event.timezone = None
            event.duration_minutes = None
        else:  # datetime
            # Parse datetime string (format: YYYY-MM-DD HH:MM or YYYY-MM-DDTHH:MM from datetime-local)
            datetime_str = form.event_datetime.data.strip()
            # Handle both formats: YYYY-MM-DD HH:MM and YYYY-MM-DDTHH:MM
            datetime_str = datetime_str.replace("T", " ")
            try:
                event_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
                event.event_datetime = event_datetime
                event.event_date = None
                # Use selected timezone from form
                event.timezone = form.timezone.data if form.timezone.data else signup_list.creator.time_zone
                # Handle duration_minutes - can be None (optional) or an integer
                if (
                    form.duration_minutes.data is not None
                    and form.duration_minutes.data != ""
                ):
                    event.duration_minutes = int(form.duration_minutes.data)
                else:
                    event.duration_minutes = None
            except ValueError:
                flash(
                    "Invalid date/time format. Please use YYYY-MM-DD HH:MM format.",
                    "error",
                )
                return render_template(
                    "better_signups/event_form.html",
                    form=form,
                    list=signup_list,
                    event=event,
                )

        db.session.commit()

        flash(f"Event updated successfully!", "success")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))
    else:
        # Show form errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", "error")

    return render_template(
        "better_signups/event_form.html", form=form, list=signup_list, event=event
    )


@bp.route("/lists/<string:uuid>/events/<int:event_id>/delete", methods=["POST"])
@login_required
def delete_event(uuid, event_id):
    """Delete an event"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    event = Event.query.get_or_404(event_id)

    # Verify event belongs to this list
    if event.list_id != signup_list.id:
        flash("Invalid event.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to delete this event.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    # Check if there are any signups
    current_signups = event.get_spots_taken()
    if current_signups > 0:
        flash(
            f"Cannot delete event with {current_signups} signup(s). Please remove signups first.",
            "error",
        )
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    db.session.delete(event)
    db.session.commit()

    flash("Event deleted successfully.", "success")
    return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))
