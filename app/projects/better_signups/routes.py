"""
Better Signups - Routes
Handles signup list creation, management, and signups
"""

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
    session,
)
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from datetime import datetime, date
from app import db
from app.forms import (
    FamilyMemberForm,
    CreateSignupListForm,
    EditSignupListForm,
    AddListEditorForm,
    EventForm,
    ItemForm,
    SignupForm,
)
from app.projects.better_signups.models import (
    FamilyMember,
    SignupList,
    ListEditor,
    Event,
    Item,
    Signup,
)
from app.projects.better_signups.utils import ensure_self_family_member
from app.models import User, LogEntry
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
    
    # Get up to 3 most recent active signups
    family_member_ids = [
        fm.id
        for fm in FamilyMember.query.filter_by(user_id=current_user.id).all()
    ]
    
    recent_signups = []
    if family_member_ids:
        recent_signups = (
            Signup.query.options(
                joinedload(Signup.event).joinedload(Event.list),
                joinedload(Signup.item).joinedload(Item.list),
                joinedload(Signup.family_member),
                joinedload(Signup.user)
            )
            .filter(
                Signup.family_member_id.in_(family_member_ids),
                Signup.cancelled_at.is_(None)
            )
            .order_by(Signup.created_at.desc())
            .limit(3)
            .all()
        )

    return render_template(
        "better_signups/index.html",
        my_lists=my_lists,
        editor_lists=editor_lists,
        recent_signups=recent_signups,
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

        # Log the action
        log_entry = LogEntry(
            project="better_signups",
            category="Add Family Member",
            actor_id=current_user.id,
            description=f"Added family member: {family_member.display_name}",
        )
        db.session.add(log_entry)
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

    # Log the action
    log_entry = LogEntry(
        project="better_signups",
        category="Delete Family Member",
        actor_id=current_user.id,
        description=f"Deleted family member: {name}",
    )
    db.session.add(log_entry)
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

        # Log the action
        password_info = "password-protected" if form.list_password.data and form.list_password.data.strip() else "public"
        log_entry = LogEntry(
            project="better_signups",
            category="Create List",
            actor_id=current_user.id,
            description=f"Created list '{new_list.name}' (type: {new_list.list_type}, {password_info}, UUID: {new_list.uuid})",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash(f'List "{new_list.name}" created successfully!', "success")
        return redirect(url_for("better_signups.edit_list", uuid=new_list.uuid))

    return render_template("better_signups/create_list.html", form=form)


@bp.route("/lists/<string:uuid>/edit", methods=["GET", "POST"])
@login_required
def edit_list(uuid):
    """View and edit a signup list (editor view)"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()

    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to view this list.", "error")
        return redirect(url_for("better_signups.index"))

    form = EditSignupListForm(obj=signup_list)
    form.accepting_signups.data = signup_list.accepting_signups

    if form.validate_on_submit():
        signup_list.name = form.name.data.strip()
        signup_list.description = (
            form.description.data.strip() if form.description.data else None
        )
        signup_list.accepting_signups = form.accepting_signups.data

        # Handle password changes
        if request.form.get("remove_password"):
            # Remove password entirely
            signup_list.list_password_hash = None
            # Also remove all existing access grants since password is gone
            from app.projects.better_signups.models import ListAccess

            ListAccess.query.filter_by(list_id=signup_list.id).delete()
            flash("Password removed! The list is now publicly accessible.", "success")
        elif form.list_password.data and form.list_password.data.strip():
            # Set new password
            signup_list.set_list_password(form.list_password.data)
        # If neither remove_password nor new password, keep existing password

        db.session.commit()

        if not request.form.get("remove_password"):
            flash(f'List "{signup_list.name}" updated successfully!', "success")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

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
        "better_signups/edit_list.html",
        list=signup_list,
        form=form,
        add_editor_form=add_editor_form,
        editors=editors,
        events=events,
    )


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
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    name = signup_list.name
    uuid = signup_list.uuid
    db.session.delete(signup_list)
    db.session.commit()

    # Log the action
    log_entry = LogEntry(
        project="better_signups",
        category="Delete List",
        actor_id=current_user.id,
        description=f"Deleted list '{name}' (UUID: {uuid})",
    )
    db.session.add(log_entry)
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
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    form = AddListEditorForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        # Try to find user by email
        user = User.query.filter_by(email=email).first()

        # Check if user is already an editor (or is the creator)
        if user and user.id == signup_list.creator_id:
            flash("The list creator is already an editor.", "error")
            return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

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
            return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

        # Add as editor (with user_id if user exists, otherwise just email)
        editor = ListEditor(
            list_id=signup_list.id, user_id=user.id if user else None, email=email
        )
        db.session.add(editor)
        db.session.commit()

        # Log the action
        log_entry = LogEntry(
            project="better_signups",
            category="Add List Editor",
            actor_id=current_user.id,
            description=f"Added editor {email} to list '{signup_list.name}' (UUID: {signup_list.uuid})",
        )
        db.session.add(log_entry)
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
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    editor = ListEditor.query.get_or_404(editor_id)

    # Verify the editor belongs to this list
    if editor.list_id != signup_list.id:
        flash("Invalid editor.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    # Get editor info before deletion
    editor_email = editor.get_display_email() or "Unknown"

    db.session.delete(editor)
    db.session.commit()

    # Log the action
    log_entry = LogEntry(
        project="better_signups",
        category="Remove List Editor",
        actor_id=current_user.id,
        description=f"Removed editor {editor_email} from list '{signup_list.name}' (UUID: {signup_list.uuid})",
    )
    db.session.add(log_entry)
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
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    # Only allow events in events-type lists
    if signup_list.list_type != "events":
        flash("This list is not configured for events.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

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
                event.timezone = (
                    form.timezone.data
                    if form.timezone.data
                    else signup_list.creator.time_zone
                )
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

        # Log the action
        event_details = []
        if event.event_type == "date":
            event_details.append(f"date: {event.event_date.strftime('%B %d, %Y')}")
        else:
            event_details.append(f"datetime: {event.event_datetime.strftime('%B %d, %Y at %I:%M %p')}")
            if event.timezone:
                event_details.append(f"timezone: {event.timezone}")
        if event.location:
            event_details.append(f"location: {event.location}")
        event_details.append(f"spots: {event.spots_available}")
        
        log_entry = LogEntry(
            project="better_signups",
            category="Add Event",
            actor_id=current_user.id,
            description=f"Added event to list '{signup_list.name}' (UUID: {signup_list.uuid}): {', '.join(event_details)}",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash(f"Event added successfully!", "success")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))
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
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to edit this event.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

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
            form.timezone.data = (
                event.timezone if event.timezone else signup_list.creator.time_zone
            )
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
                event.timezone = (
                    form.timezone.data
                    if form.timezone.data
                    else signup_list.creator.time_zone
                )
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
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))
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
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to delete this event.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    # Check if there are any signups
    current_signups = event.get_spots_taken()
    if current_signups > 0:
        flash(
            f"Cannot delete event with {current_signups} signup(s). Please remove signups first.",
            "error",
        )
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    # Get event details before deletion for logging
    event_details = []
    if event.event_type == "date":
        event_details.append(f"date: {event.event_date.strftime('%B %d, %Y')}")
    else:
        event_details.append(f"datetime: {event.event_datetime.strftime('%B %d, %Y at %I:%M %p')}")
    if event.location:
        event_details.append(f"location: {event.location}")
    
    db.session.delete(event)
    db.session.commit()

    # Log the action
    log_entry = LogEntry(
        project="better_signups",
        category="Delete Event",
        actor_id=current_user.id,
        description=f"Deleted event from list '{signup_list.name}' (UUID: {signup_list.uuid}): {', '.join(event_details)}",
    )
    db.session.add(log_entry)
    db.session.commit()

    flash("Event deleted successfully.", "success")
    return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))


@bp.route("/lists/<string:uuid>/items/add", methods=["GET", "POST"])
@login_required
def add_item(uuid):
    """Add an item to a signup list"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()

    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to add items to this list.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    # Only allow items in items-type lists
    if signup_list.list_type != "items":
        flash("This list is not configured for items.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    form = ItemForm()

    if form.validate_on_submit():
        item = Item(
            list_id=signup_list.id,
            name=form.name.data.strip(),
            description=(
                form.description.data.strip() if form.description.data else None
            ),
            spots_available=form.spots_available.data,
        )

        db.session.add(item)
        db.session.commit()

        # Log the action
        log_entry = LogEntry(
            project="better_signups",
            category="Add Item",
            actor_id=current_user.id,
            description=f"Added item '{item.name}' (spots: {item.spots_available}) to list '{signup_list.name}' (UUID: {signup_list.uuid})",
        )
        db.session.add(log_entry)
        db.session.commit()

        flash(f'Item "{item.name}" added successfully!', "success")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    return render_template(
        "better_signups/item_form.html", form=form, list=signup_list, item=None
    )


@bp.route("/lists/<string:uuid>/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(uuid, item_id):
    """Edit an item"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    item = Item.query.get_or_404(item_id)

    # Verify item belongs to this list
    if item.list_id != signup_list.id:
        flash("Invalid item.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to edit this item.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    # Only allow items in items-type lists
    if signup_list.list_type != "items":
        flash("This list is not configured for items.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    # Populate form with existing data on GET request
    if request.method == "GET":
        form = ItemForm(obj=item)
    else:
        # POST request - use submitted form data
        form = ItemForm()

    if form.validate_on_submit():
        # Check if reducing spots below current signups
        current_signups = item.get_spots_taken()
        if form.spots_available.data < current_signups:
            flash(
                f"Cannot reduce spots below current signups ({current_signups}).",
                "error",
            )
            return render_template(
                "better_signups/item_form.html", form=form, list=signup_list, item=item
            )

        # Update item
        item.name = form.name.data.strip()
        item.description = (
            form.description.data.strip() if form.description.data else None
        )
        item.spots_available = form.spots_available.data

        db.session.commit()

        flash(f'Item "{item.name}" updated successfully!', "success")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    return render_template(
        "better_signups/item_form.html", form=form, list=signup_list, item=item
    )


@bp.route("/lists/<string:uuid>/items/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(uuid, item_id):
    """Delete an item"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    item = Item.query.get_or_404(item_id)

    # Verify item belongs to this list
    if item.list_id != signup_list.id:
        flash("Invalid item.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to delete this item.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    # Only allow items in items-type lists
    if signup_list.list_type != "items":
        flash("This list is not configured for items.", "error")
        return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))

    # Check if there are any signups
    current_signups = item.get_spots_taken()
    if current_signups > 0:
        flash(
            f"Cannot delete item with {current_signups} signup(s). Please remove signups first.",
            "error",
        )
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

    item_name = item.name
    db.session.delete(item)
    db.session.commit()

    # Log the action
    log_entry = LogEntry(
        project="better_signups",
        category="Delete Item",
        actor_id=current_user.id,
        description=f"Deleted item '{item_name}' from list '{signup_list.name}' (UUID: {signup_list.uuid})",
    )
    db.session.add(log_entry)
    db.session.commit()

    flash(f'Item "{item_name}" deleted successfully.', "success")
    return redirect(url_for("better_signups.view_list", uuid=signup_list.uuid))


# Phase 7: List Viewing Routes


@bp.route("/lists/<string:uuid>", methods=["GET", "POST"])
def view_list(uuid):
    """Public view of a signup list by UUID (signup interface)"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()

    # Check if user is logged in
    if not current_user.is_authenticated:
        # Store the intended URL so we can redirect back after login
        session["next"] = url_for("better_signups.view_list", uuid=uuid)
        flash("Please log in to view this list.", "info")
        return redirect(url_for("auth.login"))

    # Check if user has access to this list
    # Editors (including creators) bypass password requirements
    if not signup_list.is_editor(current_user) and not signup_list.user_has_access(
        current_user
    ):
        # User is not an editor and doesn't have access to password-protected list
        # Show password form
        if request.method == "POST":
            password = request.form.get("password", "").strip()
            if signup_list.check_list_password(password):
                # Password correct - grant permanent access
                signup_list.grant_user_access(current_user)
                flash("Access granted! You can now view this list.", "success")
                return redirect(url_for("better_signups.view_list", uuid=uuid))
            else:
                flash("Incorrect password. Please try again.", "error")

        # Show password form
        return render_template("better_signups/password_prompt.html", list=signup_list)

    # User has access - show the list view
    # Ensure user has a "self" family member
    ensure_self_family_member(current_user)

    # Get user's family members for signup forms
    family_members = (
        FamilyMember.query.filter_by(user_id=current_user.id)
        .order_by(FamilyMember.is_self.desc(), FamilyMember.created_at)
        .all()
    )

    # Pre-compute available family members for each element to avoid template complexity
    # This will be a dict: {element_id: [available_family_member_ids]}
    available_family_members_by_element = {}

    # For events
    for event in signup_list.events:
        signed_up_family_member_ids = {
            signup.family_member_id
            for signup in event.get_active_signups()
            if signup.user_id == current_user.id
        }
        available_family_members_by_element[f"event_{event.id}"] = [
            member.id
            for member in family_members
            if member.id not in signed_up_family_member_ids
        ]

    # For items
    for item in signup_list.items:
        signed_up_family_member_ids = {
            signup.family_member_id
            for signup in item.get_active_signups()
            if signup.user_id == current_user.id
        }
        available_family_members_by_element[f"item_{item.id}"] = [
            member.id
            for member in family_members
            if member.id not in signed_up_family_member_ids
        ]

    return render_template(
        "better_signups/view_list.html",
        list=signup_list,
        family_members=family_members,
        available_family_members_by_element=available_family_members_by_element,
    )


@bp.route("/lists/<string:uuid>/signup", methods=["POST"])
@login_required
def create_signup(uuid):
    """Create a signup for an event or item"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()

    # Check if user has access
    if not signup_list.is_editor(current_user) and not signup_list.user_has_access(
        current_user
    ):
        flash("You do not have access to this list.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if list is accepting signups
    if not signup_list.accepting_signups:
        flash("This list is not currently accepting signups.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Get element type and ID from form
    element_type = request.form.get("element_type")  # 'event' or 'item'
    element_id = request.form.get("element_id")

    if not element_type or not element_id:
        flash("Invalid signup request.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    try:
        element_id = int(element_id)
    except ValueError:
        flash("Invalid element ID.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Get the element (event or item)
    if element_type == "event":
        element = Event.query.get_or_404(element_id)
        if element.list_id != signup_list.id:
            flash("Invalid event.", "error")
            return redirect(url_for("better_signups.view_list", uuid=uuid))
    elif element_type == "item":
        element = Item.query.get_or_404(element_id)
        if element.list_id != signup_list.id:
            flash("Invalid item.", "error")
            return redirect(url_for("better_signups.view_list", uuid=uuid))
    else:
        flash("Invalid element type.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if spots are available
    if element.get_spots_remaining() <= 0:
        flash("No spots available for this element.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Get family member ID from form
    family_member_id = request.form.get("family_member_id")
    if not family_member_id:
        flash("Please select a family member.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    try:
        family_member_id = int(family_member_id)
    except ValueError:
        flash("Invalid family member.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Verify family member belongs to current user
    family_member = FamilyMember.query.get_or_404(family_member_id)
    if family_member.user_id != current_user.id:
        flash("You can only sign up your own family members.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if this family member is already signed up for this element (active signup)
    if element_type == "event":
        existing_signup = Signup.query.filter_by(
            event_id=element_id, family_member_id=family_member_id, cancelled_at=None
        ).first()
        # Also check for cancelled signup (to reactivate it)
        cancelled_signup = Signup.query.filter(
            Signup.event_id == element_id,
            Signup.family_member_id == family_member_id,
            Signup.cancelled_at.isnot(None),
        ).first()
    else:
        existing_signup = Signup.query.filter_by(
            item_id=element_id, family_member_id=family_member_id, cancelled_at=None
        ).first()
        # Also check for cancelled signup (to reactivate it)
        cancelled_signup = Signup.query.filter(
            Signup.item_id == element_id,
            Signup.family_member_id == family_member_id,
            Signup.cancelled_at.isnot(None),
        ).first()

    if existing_signup:
        flash(
            f"{family_member.display_name} is already signed up for this element.",
            "error",
        )
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # If there's a cancelled signup, reactivate it instead of creating a new one
    if cancelled_signup:
        cancelled_signup.cancelled_at = None
        db.session.commit()
        
        # Log the action (reactivation)
        element_desc = ""
        if element_type == "event":
            if element.event_type == "date":
                element_desc = f"event date: {element.event_date.strftime('%B %d, %Y')}"
            else:
                element_desc = f"event datetime: {element.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
        else:
            element_desc = f"item: {element.name}"
        
        log_entry = LogEntry(
            project="better_signups",
            category="Create Signup",
            actor_id=current_user.id,
            description=f"Reactivated signup for {family_member.display_name} on list '{signup_list.name}' (UUID: {signup_list.uuid}), {element_desc}",
        )
        db.session.add(log_entry)
        db.session.commit()
        
        flash(f"Successfully signed up {family_member.display_name}!", "success")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Create a new signup
    signup = Signup(
        user_id=current_user.id,
        family_member_id=family_member_id,
    )

    if element_type == "event":
        signup.event_id = element_id
    else:
        signup.item_id = element_id

    db.session.add(signup)
    db.session.commit()

    # Log the action
    element_desc = ""
    if element_type == "event":
        if element.event_type == "date":
            element_desc = f"event date: {element.event_date.strftime('%B %d, %Y')}"
        else:
            element_desc = f"event datetime: {element.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
    else:
        element_desc = f"item: {element.name}"
    
    log_entry = LogEntry(
        project="better_signups",
        category="Create Signup",
        actor_id=current_user.id,
        description=f"Signed up {family_member.display_name} for list '{signup_list.name}' (UUID: {signup_list.uuid}), {element_desc}",
    )
    db.session.add(log_entry)
    db.session.commit()

    flash(f"Successfully signed up {family_member.display_name}!", "success")
    return redirect(url_for("better_signups.view_list", uuid=uuid))


@bp.route("/lists/<string:uuid>/signup/<int:signup_id>/cancel", methods=["POST"])
@login_required
def cancel_signup(uuid, signup_id):
    """Cancel a signup"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    signup = Signup.query.get_or_404(signup_id)

    # Verify signup belongs to an element in this list
    if signup.event_id:
        event = Event.query.get_or_404(signup.event_id)
        if event.list_id != signup_list.id:
            flash("Invalid signup.", "error")
            return redirect(url_for("better_signups.view_list", uuid=uuid))
    elif signup.item_id:
        item = Item.query.get_or_404(signup.item_id)
        if item.list_id != signup_list.id:
            flash("Invalid signup.", "error")
            return redirect(url_for("better_signups.view_list", uuid=uuid))
    else:
        flash("Invalid signup.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Verify user owns this signup (or is an editor)
    if not signup_list.is_editor(current_user) and signup.user_id != current_user.id:
        flash("You can only cancel your own signups.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if already cancelled
    if signup.cancelled_at:
        flash("This signup has already been cancelled.", "info")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Get element details before cancellation for logging
    element_desc = ""
    if signup.event_id:
        # event was already queried above
        if event.event_type == "date":
            element_desc = f"event date: {event.event_date.strftime('%B %d, %Y')}"
        else:
            element_desc = f"event datetime: {event.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
    elif signup.item_id:
        # item was already queried above
        element_desc = f"item: {item.name}"
    
    # Cancel the signup
    signup.cancel()
    db.session.commit()

    family_member_name = (
        signup.family_member.display_name if signup.family_member else "Unknown"
    )
    
    # Log the action
    cancelled_by = "themselves" if signup.user_id == current_user.id else f"editor {current_user.email}"
    log_entry = LogEntry(
        project="better_signups",
        category="Cancel Signup",
        actor_id=current_user.id,
        description=f"Cancelled signup for {family_member_name} (cancelled by {cancelled_by}) on list '{signup_list.name}' (UUID: {signup_list.uuid}), {element_desc}",
    )
    db.session.add(log_entry)
    db.session.commit()
    
    flash(f"Successfully cancelled signup for {family_member_name}.", "success")
    
    # Check if we should redirect back to my-signups page
    next_url = request.form.get("next") or request.args.get("next")
    if next_url and "my-signups" in next_url:
        return redirect(url_for("better_signups.my_signups"))
    
    return redirect(url_for("better_signups.view_list", uuid=uuid))


@bp.route("/my-signups")
@login_required
def my_signups():
    """View all active signups for the current user and their family members"""
    # Get all family member IDs for current user
    family_member_ids = [
        fm.id
        for fm in FamilyMember.query.filter_by(user_id=current_user.id).all()
    ]
    
    if not family_member_ids:
        # No family members yet (shouldn't happen if self is auto-created, but handle it)
        ensure_self_family_member(current_user)
        family_member_ids = [
            fm.id
            for fm in FamilyMember.query.filter_by(user_id=current_user.id).all()
        ]
    
    # Get all active signups (not cancelled) for these family members
    # Order by created_at descending (most recent first)
    # Eager load related data to avoid N+1 queries
    signups = (
        Signup.query.options(
            joinedload(Signup.event).joinedload(Event.list),
            joinedload(Signup.item).joinedload(Item.list),
            joinedload(Signup.family_member),
            joinedload(Signup.user)
        )
        .filter(
            Signup.family_member_id.in_(family_member_ids),
            Signup.cancelled_at.is_(None)
        )
        .order_by(Signup.created_at.desc())
        .all()
    )
    
    return render_template("better_signups/my_signups.html", signups=signups)
