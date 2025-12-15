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
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
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
    SwapRequest,
    SwapRequestTarget,
    SwapToken,
    WaitlistEntry,
)
from app.projects.better_signups.utils import (
    ensure_self_family_member,
    get_google_calendar_url,
    check_has_eligible_swap_targets,
)
from app.models import User, LogEntry
from app.utils.email_service import send_swap_request_email
import pytz
import logging

logger = logging.getLogger(__name__)

bp = Blueprint(
    "better_signups",
    __name__,
    url_prefix="/better-signups",
    template_folder="templates",
    static_folder="static",
)


# ============================================================================
# Helper Functions
# ============================================================================


def offer_spot_to_next_in_waitlist(element_type, element_id):
    """
    Offer a spot to the next person on the waitlist for an element.
    
    This function:
    1. Finds people on the waitlist (ordered by position)
    2. Checks if they're at their signup limit for the list
    3. Skips people at limit (logs, keeps them on waitlist)
    4. Creates a pending_confirmation signup for first eligible person
    5. Deletes their waitlist entry
    6. Returns info about the offered signup for email notification
    
    Args:
        element_type: 'event' or 'item'
        element_id: ID of the event or item
        
    Returns:
        dict with signup info if someone was offered, None if waitlist is empty or everyone is at limit
        {
            'signup': Signup object,
            'user': User object,
            'family_member': FamilyMember object,
            'element': Event or Item object
        }
    """
    from app.projects.better_signups.utils import is_at_limit
    
    try:
        # Get the element to determine the list_id
        if element_type == "event":
            element = Event.query.get(element_id)
        else:
            element = Item.query.get(element_id)
            
        if not element:
            logger.error(f"Element not found: {element_type} {element_id}")
            return None
        
        list_id = element.list_id
        
        # Query for all waitlist entries for this element, ordered by position
        waitlist_entries = (
            WaitlistEntry.query.filter_by(
                element_type=element_type,
                element_id=element_id,
            )
            .order_by(WaitlistEntry.position.asc())
            .all()
        )
        
        if not waitlist_entries:
            # No one on waitlist, spot opens to everyone
            logger.info(f"No waitlist entries found for {element_type} {element_id}")
            return None
        
        # Iterate through waitlist entries to find someone below the limit
        for waitlist_entry in waitlist_entries:
            family_member = waitlist_entry.family_member
            user = family_member.user
            
            # Check if this family member is at their signup limit
            if is_at_limit(family_member.id, list_id):
                # Skip this person - they're at their limit
                logger.info(
                    f"Skipping {family_member.display_name} (user {user.id}) on waitlist "
                    f"for {element_type} {element_id} - at signup limit"
                )
                
                # Log the skip event
                log_entry = LogEntry(
                    project="better_signups",
                    category="Waitlist Limit Skip",
                    actor_id=user.id,
                    description=f"Skipped offering spot to {family_member.display_name} from waitlist - at signup limit for list",
                )
                db.session.add(log_entry)
                db.session.commit()
                
                # Continue to next person in waitlist (keep this person on waitlist)
                continue
            
            # This person is below the limit - offer them the spot
            
            # Create pending_confirmation signup
            signup = Signup(
                user_id=user.id,
                family_member_id=family_member.id,
                status='pending_confirmation',
            )
            
            if element_type == "event":
                signup.event_id = element_id
            else:
                signup.item_id = element_id
            
            # Delete the waitlist entry (they're no longer waiting)
            db.session.delete(waitlist_entry)
            
            # Add signup
            db.session.add(signup)
            
            # Log the cascade event
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
                category="Waitlist Cascade",
                actor_id=user.id,
                description=f"Offered spot to {family_member.display_name} from waitlist (position #{waitlist_entry.position}), {element_desc}",
            )
            db.session.add(log_entry)
            
            # Commit the transaction
            db.session.commit()
            
            logger.info(
                f"Offered spot to {family_member.display_name} (user {user.id}) "
                f"for {element_type} {element_id}, position was #{waitlist_entry.position}"
            )
            
            # Return info for email notification
            return {
                'signup': signup,
                'user': user,
                'family_member': family_member,
                'element': element,
                'element_type': element_type,
            }
        
        # If we get here, everyone on the waitlist is at their limit
        logger.info(
            f"All {len(waitlist_entries)} people on waitlist for {element_type} {element_id} "
            f"are at their signup limit. Spot opens to everyone."
        )
        return None
        
    except Exception as e:
        logger.error(f"Error in offer_spot_to_next_in_waitlist: {str(e)}")
        db.session.rollback()
        return None


def send_waitlist_offer_email(cascade_result):
    """
    Send email notification when someone is offered a spot from the waitlist.
    
    Args:
        cascade_result: dict returned from offer_spot_to_next_in_waitlist()
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        from app.utils.email_service import send_waitlist_spot_offered_email
        from datetime import timedelta
        
        signup = cascade_result['signup']
        user = cascade_result['user']
        family_member = cascade_result['family_member']
        element = cascade_result['element']
        
        # Get the list
        if signup.event_id:
            list_obj = element.list
        else:
            list_obj = element.list
        
        # Calculate deadline (24 hours from creation)
        deadline = signup.created_at + timedelta(hours=24)
        
        # Send email
        send_waitlist_spot_offered_email(
            user=user,
            family_member=family_member,
            element=element,
            list_obj=list_obj,
            deadline=deadline
        )
        
        logger.info(f"Sent waitlist offer email to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send waitlist offer email: {e}")
        return False


# ============================================================================
# Routes
# ============================================================================


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
        fm.id for fm in FamilyMember.query.filter_by(user_id=current_user.id).all()
    ]

    recent_signups = []
    if family_member_ids:
        recent_signups = (
            Signup.query.options(
                joinedload(Signup.event).joinedload(Event.list),
                joinedload(Signup.item).joinedload(Item.list),
                joinedload(Signup.family_member),
                joinedload(Signup.user),
            )
            .filter(
                Signup.family_member_id.in_(family_member_ids),
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

        # Log the action (combine with add commit)
        log_entry = LogEntry(
            project="better_signups",
            category="Add Family Member",
            actor_id=current_user.id,
            description=f"Added family member: {family_member.display_name}",
        )
        db.session.add(log_entry)

        # Commit both family member creation and log together
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("An error occurred while adding the family member. Please try again.", "error")
            return redirect(url_for("better_signups.family_members"))

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
    active_signups = family_member.signups
    if active_signups:
        flash(
            f'Cannot delete "{family_member.display_name}" because they have active signups. '
            "Please cancel all signups first.",
            "error",
        )
        return redirect(url_for("better_signups.family_members"))

    name = family_member.display_name

    # Log the action before deletion (combine with delete commit)
    log_entry = LogEntry(
        project="better_signups",
        category="Delete Family Member",
        actor_id=current_user.id,
        description=f"Deleted family member: {name}",
    )
    db.session.add(log_entry)
    db.session.delete(family_member)

    # Commit both deletion and log together
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while deleting the family member. Please try again.", "error")
        return redirect(url_for("better_signups.family_members"))

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
            allow_waitlist=form.allow_waitlist.data,
            max_signups_per_member=form.max_signups_per_member.data if form.max_signups_per_member.data else None,
        )

        # Generate UUID
        new_list.generate_uuid()

        # Set password if provided
        if form.list_password.data and form.list_password.data.strip():
            new_list.set_list_password(form.list_password.data)

        db.session.add(new_list)

        # Log the action (combine with create commit)
        password_info = (
            "password-protected"
            if form.list_password.data and form.list_password.data.strip()
            else "public"
        )
        waitlist_info = "waitlist enabled" if form.allow_waitlist.data else "no waitlist"
        limit_info = f"limit: {new_list.max_signups_per_member} per person" if new_list.max_signups_per_member else "no limit"
        log_entry = LogEntry(
            project="better_signups",
            category="Create List",
            actor_id=current_user.id,
            description=f"Created list '{new_list.name}' (type: {new_list.list_type}, {password_info}, {waitlist_info}, {limit_info}, UUID: {new_list.uuid})",
        )
        db.session.add(log_entry)

        # Commit both list creation and log together
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("An error occurred while creating the list. Please try again.", "error")
            return render_template("better_signups/create_list.html", form=form)

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
        flash("You do not have permission to edit this list.", "error")
        return redirect(url_for("better_signups.index"))

    form = EditSignupListForm(obj=signup_list)
    
    # Only pre-populate checkbox values on GET requests
    # On POST, let the form get values from request data
    if request.method == 'GET':
        form.accepting_signups.data = signup_list.accepting_signups
        form.allow_waitlist.data = signup_list.allow_waitlist
        form.max_signups_per_member.data = signup_list.max_signups_per_member

    if form.validate_on_submit():
        # Validate waitlist can be disabled
        if not form.allow_waitlist.data and signup_list.allow_waitlist:
            # User is trying to disable waitlist - check if any waitlist entries exist
            waitlist_count = WaitlistEntry.query.filter_by(list_id=signup_list.id).count()
            if waitlist_count > 0:
                flash(
                    f"Cannot disable waitlist: {waitlist_count} people are currently on waitlists. "
                    "Remove all waitlist entries first.",
                    "error"
                )
                return render_template(
                    "better_signups/edit_list.html",
                    list=signup_list,
                    form=form,
                    add_editor_form=AddListEditorForm() if signup_list.creator_id == current_user.id else None,
                    editors=ListEditor.query.filter_by(list_id=signup_list.id).all(),
                    events=Event.query.options(
                        joinedload(Event.signups).joinedload(Signup.user),
                        joinedload(Event.signups).joinedload(Signup.family_member),
                    ).filter_by(list_id=signup_list.id).order_by(
                        Event.event_date.asc().nullslast(), Event.event_datetime.asc().nullslast()
                    ).all() if signup_list.list_type == "events" else [],
                    items=Item.query.options(
                        joinedload(Item.signups).joinedload(Signup.user),
                        joinedload(Item.signups).joinedload(Signup.family_member),
                    ).filter_by(list_id=signup_list.id).order_by(Item.created_at.asc()).all() if signup_list.list_type == "items" else [],
                    waitlist_entries_by_element={},
                )
        
        signup_list.name = form.name.data.strip()
        signup_list.description = (
            form.description.data.strip() if form.description.data else None
        )
        signup_list.accepting_signups = form.accepting_signups.data
        signup_list.allow_waitlist = form.allow_waitlist.data
        signup_list.max_signups_per_member = form.max_signups_per_member.data if form.max_signups_per_member.data else None

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
    # Eager load signups with user and family_member to avoid N+1 queries
    events = (
        Event.query.options(
            joinedload(Event.signups).joinedload(Signup.user),
            joinedload(Event.signups).joinedload(Signup.family_member),
        )
        .filter_by(list_id=signup_list.id)
        .order_by(
            Event.event_date.asc().nullslast(), Event.event_datetime.asc().nullslast()
        )
        .all()
        if signup_list.list_type == "events"
        else []
    )

    # Get items if this is an items list
    # Eager load signups with user and family_member to avoid N+1 queries
    items = (
        Item.query.options(
            joinedload(Item.signups).joinedload(Signup.user),
            joinedload(Item.signups).joinedload(Signup.family_member),
        )
        .filter_by(list_id=signup_list.id)
        .order_by(Item.created_at.asc())
        .all()
        if signup_list.list_type == "items"
        else []
    )

    # Get waitlist entries if waitlist is enabled
    waitlist_entries_by_element = {}
    if signup_list.allow_waitlist:
        all_waitlist_entries = (
            WaitlistEntry.query.options(
                joinedload(WaitlistEntry.family_member).joinedload(FamilyMember.user)
            )
            .filter_by(list_id=signup_list.id)
            .order_by(WaitlistEntry.position)
            .all()
        )
        for entry in all_waitlist_entries:
            element_key = f"{entry.element_type}_{entry.element_id}"
            if element_key not in waitlist_entries_by_element:
                waitlist_entries_by_element[element_key] = []
            waitlist_entries_by_element[element_key].append(entry)

    return render_template(
        "better_signups/edit_list.html",
        list=signup_list,
        form=form,
        add_editor_form=add_editor_form,
        editors=editors,
        events=events,
        items=items if signup_list.list_type == "items" else [],
        waitlist_entries_by_element=waitlist_entries_by_element,
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

    # Cancel all pending swap requests for this list (automatic cleanup)
    pending_swap_requests = SwapRequest.query.filter_by(
        list_id=signup_list.id,
        status="pending"
    ).all()
    
    for swap_req in pending_swap_requests:
        swap_req.status = "cancelled"
        # Invalidate all associated tokens
        for token in swap_req.tokens:
            if not token.is_used:
                token.is_used = True
                token.used_at = datetime.utcnow()

    # Log the action before deletion (combine with delete commit)
    log_entry = LogEntry(
        project="better_signups",
        category="Delete List",
        actor_id=current_user.id,
        description=f"Deleted list '{name}' (UUID: {uuid})",
    )
    db.session.add(log_entry)
    db.session.delete(signup_list)

    # Commit both deletion and log together
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while deleting the list. Please try again.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

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

        # Log the action (combine with add commit)
        log_entry = LogEntry(
            project="better_signups",
            category="Add List Editor",
            actor_id=current_user.id,
            description=f"Added editor {email} to list '{signup_list.name}' (UUID: {signup_list.uuid})",
        )
        db.session.add(log_entry)

        # Commit both editor addition and log together
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("An error occurred while adding the editor. Please try again.", "error")
            return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

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

    # Log the action before deletion (combine with delete commit)
    log_entry = LogEntry(
        project="better_signups",
        category="Remove List Editor",
        actor_id=current_user.id,
        description=f"Removed editor {editor_email} from list '{signup_list.name}' (UUID: {signup_list.uuid})",
    )
    db.session.add(log_entry)
    db.session.delete(editor)

    # Commit both deletion and log together
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while removing the editor. Please try again.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

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

        # Log the action (combine with add commit)
        event_details = []
        if event.event_type == "date":
            event_details.append(f"date: {event.event_date.strftime('%B %d, %Y')}")
        else:
            event_details.append(
                f"datetime: {event.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
            )
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

        # Commit both event creation and log together
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("An error occurred while adding the event. Please try again.", "error")
            return render_template(
                "better_signups/event_form.html",
                form=form,
                list=signup_list,
                event=None,
            )

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

    # Handle swap request cleanup when target element is deleted
    # Find all pending swap requests that target this event
    pending_swap_requests = SwapRequest.query.filter_by(
        list_id=signup_list.id,
        status="pending"
    ).all()
    
    for swap_req in pending_swap_requests:
        # Find and remove any targets for this event
        targets_to_remove = [t for t in swap_req.targets if t.target_element_type == "event" and t.target_element_id == event.id]
        
        for target in targets_to_remove:
            # Invalidate all tokens associated with this target element
            tokens_for_target = [t for t in swap_req.tokens if t.target_element_id == event.id and t.target_element_type == "event"]
            for token in tokens_for_target:
                if not token.is_used:
                    token.is_used = True
                    token.used_at = datetime.utcnow()
            
            # Remove the target
            db.session.delete(target)
        
        # If swap request has no remaining targets, cancel it
        if targets_to_remove:
            db.session.flush()  # Flush deletions
            remaining_targets = SwapRequestTarget.query.filter_by(swap_request_id=swap_req.id).count()
            if remaining_targets == 0:
                swap_req.status = "cancelled"
                # Invalidate any remaining tokens
                for token in swap_req.tokens:
                    if not token.is_used:
                        token.is_used = True
                        token.used_at = datetime.utcnow()

    # Get event details before deletion for logging
    event_details = []
    if event.event_type == "date":
        event_details.append(f"date: {event.event_date.strftime('%B %d, %Y')}")
    else:
        event_details.append(
            f"datetime: {event.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
        )
    if event.location:
        event_details.append(f"location: {event.location}")

    # Log the action before deletion (combine with delete commit)
    log_entry = LogEntry(
        project="better_signups",
        category="Delete Event",
        actor_id=current_user.id,
        description=f"Deleted event from list '{signup_list.name}' (UUID: {signup_list.uuid}): {', '.join(event_details)}",
    )
    db.session.add(log_entry)
    db.session.delete(event)

    # Commit both deletion and log together
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while deleting the event. Please try again.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

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

        # Log the action (combine with add commit)
        log_entry = LogEntry(
            project="better_signups",
            category="Add Item",
            actor_id=current_user.id,
            description=f"Added item '{item.name}' (spots: {item.spots_available}) to list '{signup_list.name}' (UUID: {signup_list.uuid})",
        )
        db.session.add(log_entry)

        # Commit both item creation and log together
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("An error occurred while adding the item. Please try again.", "error")
            return render_template(
                "better_signups/item_form.html", form=form, list=signup_list, item=None
            )

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

    # Handle swap request cleanup when target element is deleted
    # Find all pending swap requests that target this item
    pending_swap_requests = SwapRequest.query.filter_by(
        list_id=signup_list.id,
        status="pending"
    ).all()
    
    for swap_req in pending_swap_requests:
        # Find and remove any targets for this item
        targets_to_remove = [t for t in swap_req.targets if t.target_element_type == "item" and t.target_element_id == item.id]
        
        for target in targets_to_remove:
            # Invalidate all tokens associated with this target element
            tokens_for_target = [t for t in swap_req.tokens if t.target_element_id == item.id and t.target_element_type == "item"]
            for token in tokens_for_target:
                if not token.is_used:
                    token.is_used = True
                    token.used_at = datetime.utcnow()
            
            # Remove the target
            db.session.delete(target)
        
        # If swap request has no remaining targets, cancel it
        if targets_to_remove:
            db.session.flush()  # Flush deletions
            remaining_targets = SwapRequestTarget.query.filter_by(swap_request_id=swap_req.id).count()
            if remaining_targets == 0:
                swap_req.status = "cancelled"
                # Invalidate any remaining tokens
                for token in swap_req.tokens:
                    if not token.is_used:
                        token.is_used = True
                        token.used_at = datetime.utcnow()

    item_name = item.name

    # Log the action before deletion (combine with delete commit)
    log_entry = LogEntry(
        project="better_signups",
        category="Delete Item",
        actor_id=current_user.id,
        description=f"Deleted item '{item_name}' from list '{signup_list.name}' (UUID: {signup_list.uuid})",
    )
    db.session.add(log_entry)
    db.session.delete(item)

    # Commit both deletion and log together
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while deleting the item. Please try again.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=signup_list.uuid))

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
    # Process any expired pending confirmations before showing the list
    from app.projects.better_signups.utils import process_expired_pending_confirmations
    process_expired_pending_confirmations()
    
    # Ensure user has a "self" family member
    ensure_self_family_member(current_user)

    # Get user's family members for signup forms
    family_members = (
        FamilyMember.query.filter_by(user_id=current_user.id)
        .order_by(FamilyMember.is_self.desc(), FamilyMember.created_at)
        .all()
    )
    
    # Calculate signup counts for each family member (for limit display)
    from app.projects.better_signups.utils import get_signup_count
    family_member_signup_counts = {}
    for fm in family_members:
        family_member_signup_counts[fm.id] = get_signup_count(fm.id, signup_list.id)

    # Pre-compute available family members for each element to avoid template complexity
    # This will be a dict: {element_id: [available_family_member_ids]}
    available_family_members_by_element = {}
    
    # Track which elements the current user has signed up for (any family member)
    user_signed_up_element_ids = set()
    
    # Track which signup IDs belong to the current user's family members
    user_family_signup_ids = set()
    
    # Get all waitlist entries for this list
    waitlist_entries_by_element = {}
    user_waitlist_entries = {}  # Track which elements user's family members are on waitlist for
    
    if signup_list.allow_waitlist:
        all_waitlist_entries = WaitlistEntry.query.filter_by(list_id=signup_list.id).order_by(WaitlistEntry.position).all()
        for entry in all_waitlist_entries:
            element_key = f"{entry.element_type}_{entry.element_id}"
            if element_key not in waitlist_entries_by_element:
                waitlist_entries_by_element[element_key] = []
            waitlist_entries_by_element[element_key].append(entry)
            
            # Track if current user's family member is on this waitlist
            if entry.family_member.user_id == current_user.id:
                if element_key not in user_waitlist_entries:
                    user_waitlist_entries[element_key] = []
                user_waitlist_entries[element_key].append(entry)

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
        
        # Check if user has any family member signed up for this event
        if signed_up_family_member_ids:
            user_signed_up_element_ids.add(f"event_{event.id}")
        
        # Track signup IDs for this user's family members
        for signup in event.get_active_signups():
            if signup.user_id == current_user.id:
                user_family_signup_ids.add(signup.id)

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
        
        # Check if user has any family member signed up for this item
        if signed_up_family_member_ids:
            user_signed_up_element_ids.add(f"item_{item.id}")
        
        # Track signup IDs for this user's family members
        for signup in item.get_active_signups():
            if signup.user_id == current_user.id:
                user_family_signup_ids.add(signup.id)

    # Generate Google Calendar URLs for all events (date and datetime)
    # We'll attach URLs to events so the template can use them
    for event in signup_list.events:
        event.google_calendar_url = get_google_calendar_url(event, signup_list.name, current_user)

    # Check for pending confirmations for this user
    family_member_ids = [fm.id for fm in family_members]
    pending_confirmations = []
    if family_member_ids:
        from datetime import timedelta
        pending_confirmations = (
            Signup.query.options(
                joinedload(Signup.event),
                joinedload(Signup.item),
                joinedload(Signup.family_member),
            )
            .filter(
                Signup.family_member_id.in_(family_member_ids),
                Signup.status == 'pending_confirmation',
            )
            .all()
        )
        # Attach deadline info to each pending confirmation
        for pending in pending_confirmations:
            pending.deadline = pending.created_at + timedelta(hours=24)
            pending.is_expired = pending.deadline < datetime.utcnow()

    return render_template(
        "better_signups/view_list.html",
        list=signup_list,
        family_members=family_members,
        available_family_members_by_element=available_family_members_by_element,
        user_signed_up_element_ids=user_signed_up_element_ids,
        user_family_signup_ids=user_family_signup_ids,
        waitlist_entries_by_element=waitlist_entries_by_element,
        user_waitlist_entries=user_waitlist_entries,
        pending_confirmations=pending_confirmations,
        family_member_signup_counts=family_member_signup_counts,
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

    # Check if spots are available by querying database directly (not using relationship)
    # This ensures we get the most up-to-date count
    if element_type == "event":
        active_count = (
            db.session.query(Signup)
            .filter(Signup.event_id == element_id)
            .count()
        )
    else:
        active_count = (
            db.session.query(Signup)
            .filter(Signup.item_id == element_id)
            .count()
        )
    
    spots_remaining = element.spots_available - active_count
    if spots_remaining <= 0:
        flash("No spots available for this element. It may have just filled up.", "error")
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

    # Check if family member is at their signup limit for this list
    from app.projects.better_signups.utils import is_at_limit, get_signup_count
    
    if is_at_limit(family_member_id, signup_list.id):
        current_count = get_signup_count(family_member_id, signup_list.id)
        flash(
            f"Cannot sign up {family_member.display_name} - they have already signed up for the maximum number "
            f"of {signup_list.list_type} in this list ({current_count}/{signup_list.max_signups_per_member}). "
            f"Please cancel one of their existing signups first.",
            "error"
        )
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if this family member is already signed up for this element (active signup)
    if element_type == "event":
        existing_signup = Signup.query.filter_by(
            event_id=element_id, family_member_id=family_member_id
        ).first()
    else:
        existing_signup = Signup.query.filter_by(
            item_id=element_id, family_member_id=family_member_id
        ).first()

    if existing_signup:
        flash(
            f"{family_member.display_name} is already signed up for this element.",
            "error",
        )
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
    
    # Prepare logging info before commit
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

    # Race condition fix: Re-check spots by counting active signups directly from database
    # This ensures we have the latest count including any signups created by other users
    # Note: The signup we just added is in the session but not committed, so it will be included in the count
    if element_type == "event":
        active_count = (
            db.session.query(Signup)
            .filter(Signup.event_id == element_id)
            .count()
        )
    else:
        active_count = (
            db.session.query(Signup)
            .filter(Signup.item_id == element_id)
            .count()
        )
    
    # Note: active_count includes the signup we just added (it's in the session but not committed)
    # So we need to check if (active_count) > spots_available (not >=)
    # If active_count == spots_available, that's fine - we're taking the last spot
    if active_count > element.spots_available:
        db.session.rollback()
        flash("No spots available for this element. It may have just filled up.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Commit both signup and log entry together
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(
            f"{family_member.display_name} is already signed up for this element.",
            "error",
        )
        return redirect(url_for("better_signups.view_list", uuid=uuid))
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while creating your signup. Please try again.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

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

    # Get element details before deletion for logging
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

    # Cancel any pending swap requests for this signup (automatic cleanup)
    pending_swap_requests = SwapRequest.query.filter_by(
        requestor_signup_id=signup.id,
        status="pending"
    ).all()
    
    for swap_req in pending_swap_requests:
        swap_req.status = "cancelled"
        # Invalidate all associated tokens
        for token in swap_req.tokens:
            if not token.is_used:
                token.is_used = True
                token.used_at = datetime.utcnow()

    # Cancel the signup (delete it)
    family_member_name = (
        signup.family_member.display_name if signup.family_member else "Unknown"
    )
    
    # Store element info for cascade before deleting signup
    element_type_for_cascade = "event" if signup.event_id else "item"
    element_id_for_cascade = signup.event_id if signup.event_id else signup.item_id
    
    db.session.delete(signup)

    # Log the action (combine with cancel commit)
    cancelled_by = (
        "themselves"
        if signup.user_id == current_user.id
        else f"editor {current_user.email}"
    )
    log_entry = LogEntry(
        project="better_signups",
        category="Cancel Signup",
        actor_id=current_user.id,
        description=f"Cancelled signup for {family_member_name} (cancelled by {cancelled_by}) on list '{signup_list.name}' (UUID: {signup_list.uuid}), {element_desc}",
    )
    db.session.add(log_entry)

    # Commit both cancel and log together
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while cancelling your signup. Please try again.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    flash(f"Successfully cancelled signup for {family_member_name}.", "success")
    
    # After successful cancellation, check if we should offer spot to waitlist
    # Only do this if the list allows waitlist
    if signup_list.allow_waitlist:
        cascade_result = offer_spot_to_next_in_waitlist(element_type_for_cascade, element_id_for_cascade)
        if cascade_result:
            # Someone was offered the spot
            logger.info(
                f"Cascade successful: offered spot to {cascade_result['family_member'].display_name} "
                f"(user {cascade_result['user'].id})"
            )
            # Send email notification
            send_waitlist_offer_email(cascade_result)

    # Check if we should redirect back to my-signups page
    next_url = request.form.get("next") or request.args.get("next")
    if next_url and "my-signups" in next_url:
        return redirect(url_for("better_signups.my_signups"))

    return redirect(url_for("better_signups.view_list", uuid=uuid))


@bp.route("/lists/<string:uuid>/signup/<int:signup_id>/remove", methods=["POST"])
@login_required
def remove_signup(uuid, signup_id):
    """Remove a signup as an editor (removes someone else's signup)"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    signup = Signup.query.get_or_404(signup_id)

    # Verify user is an editor
    if not signup_list.is_editor(current_user):
        flash("You do not have permission to remove signups from this list.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=uuid))

    # Verify signup belongs to an element in this list
    if signup.event_id:
        event = Event.query.get_or_404(signup.event_id)
        if event.list_id != signup_list.id:
            flash("Invalid signup.", "error")
            return redirect(url_for("better_signups.edit_list", uuid=uuid))
    elif signup.item_id:
        item = Item.query.get_or_404(signup.item_id)
        if item.list_id != signup_list.id:
            flash("Invalid signup.", "error")
            return redirect(url_for("better_signups.edit_list", uuid=uuid))
    else:
        flash("Invalid signup.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=uuid))

    # Get element details before deletion for logging
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

    # Cancel any pending swap requests for this signup (automatic cleanup)
    pending_swap_requests = SwapRequest.query.filter_by(
        requestor_signup_id=signup.id,
        status="pending"
    ).all()
    
    for swap_req in pending_swap_requests:
        swap_req.status = "cancelled"
        # Invalidate all associated tokens
        for token in swap_req.tokens:
            if not token.is_used:
                token.is_used = True
                token.used_at = datetime.utcnow()

    # Cancel the signup (reuse cancel method - delete it)
    family_member_name = (
        signup.family_member.display_name if signup.family_member else "Unknown"
    )
    user_name = signup.user.full_name if signup.user else "Unknown"
    
    db.session.delete(signup)

    # Log the action (combine with cancel commit)
    log_entry = LogEntry(
        project="better_signups",
        category="Remove Signup",
        actor_id=current_user.id,
        description=f"Editor removed signup for {family_member_name} ({user_name}) on list '{signup_list.name}' (UUID: {signup_list.uuid}), {element_desc}",
    )
    db.session.add(log_entry)

    # Commit both cancel and log together
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while removing the signup. Please try again.", "error")
        return redirect(url_for("better_signups.edit_list", uuid=uuid))

    flash(
        f"Successfully removed signup for {family_member_name}.",
        "success",
    )
    return redirect(url_for("better_signups.edit_list", uuid=uuid))


@bp.route("/lists/<string:uuid>/waitlist/join", methods=["POST"])
@login_required
def join_waitlist(uuid):
    """Join a waitlist for an event or item"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()

    # Check if user has access
    if not signup_list.is_editor(current_user) and not signup_list.user_has_access(
        current_user
    ):
        flash("You do not have access to this list.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if list allows waitlist
    if not signup_list.allow_waitlist:
        flash("This list does not have waitlist enabled.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if list is accepting signups
    if not signup_list.accepting_signups:
        flash("This list is not currently accepting signups or waitlist entries.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Get form data
    element_type = request.form.get("element_type")  # 'event' or 'item'
    element_id = request.form.get("element_id", type=int)
    family_member_id = request.form.get("family_member_id", type=int)

    if not all([element_type, element_id, family_member_id]):
        flash("Missing required information.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Validate element type
    if element_type not in ["event", "item"]:
        flash("Invalid element type.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Get the element
    if element_type == "event":
        element = Event.query.get_or_404(element_id)
        if element.list_id != signup_list.id:
            flash("Invalid event.", "error")
            return redirect(url_for("better_signups.view_list", uuid=uuid))
    else:
        element = Item.query.get_or_404(element_id)
        if element.list_id != signup_list.id:
            flash("Invalid item.", "error")
            return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Verify element is full
    if element.get_spots_remaining() > 0:
        flash("This element still has spots available. Please sign up directly instead.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Verify family member belongs to current user
    family_member = FamilyMember.query.get_or_404(family_member_id)
    if family_member.user_id != current_user.id:
        flash("Invalid family member.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if family member is at their signup limit for this list
    from app.projects.better_signups.utils import is_at_limit, get_signup_count
    
    if is_at_limit(family_member_id, signup_list.id):
        current_count = get_signup_count(family_member_id, signup_list.id)
        flash(
            f"Cannot join waitlist - {family_member.display_name} has already signed up for the maximum number "
            f"of {signup_list.list_type} ({current_count}/{signup_list.max_signups_per_member}). "
            f"You can join the waitlist once they have fewer signups.",
            "error"
        )
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if this family member is already signed up for this element
    if element_type == "event":
        existing_signup = Signup.query.filter_by(
            event_id=element_id, family_member_id=family_member_id
        ).first()
    else:
        existing_signup = Signup.query.filter_by(
            item_id=element_id, family_member_id=family_member_id
        ).first()

    if existing_signup:
        flash(
            f"{family_member.display_name} is already signed up for this element.",
            "error",
        )
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if already on waitlist
    existing_waitlist = WaitlistEntry.query.filter_by(
        list_id=signup_list.id,
        element_type=element_type,
        element_id=element_id,
        family_member_id=family_member_id,
    ).first()

    if existing_waitlist:
        flash(
            f"{family_member.display_name} is already on the waitlist for this element.",
            "error",
        )
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Calculate position (max + 1, or 1 if first)
    max_position = (
        db.session.query(db.func.max(WaitlistEntry.position))
        .filter_by(
            element_type=element_type,
            element_id=element_id,
        )
        .scalar()
    )
    position = (max_position + 1) if max_position else 1

    # Create waitlist entry
    waitlist_entry = WaitlistEntry(
        list_id=signup_list.id,
        element_type=element_type,
        element_id=element_id,
        family_member_id=family_member_id,
        position=position,
    )

    db.session.add(waitlist_entry)

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
        category="Join Waitlist",
        actor_id=current_user.id,
        description=f"Added {family_member.display_name} to waitlist (position #{position}) for list '{signup_list.name}' (UUID: {signup_list.uuid}), {element_desc}",
    )
    db.session.add(log_entry)

    # Commit
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(
            f"{family_member.display_name} is already on the waitlist for this element.",
            "error",
        )
        return redirect(url_for("better_signups.view_list", uuid=uuid))
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while joining the waitlist. Please try again.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    flash(f"Successfully added {family_member.display_name} to the waitlist! You are #{position} in line.", "success")
    return redirect(url_for("better_signups.view_list", uuid=uuid))


@bp.route("/lists/<string:uuid>/waitlist/<int:entry_id>/remove", methods=["POST"])
@login_required
def remove_from_waitlist(uuid, entry_id):
    """Remove a family member from a waitlist"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    waitlist_entry = WaitlistEntry.query.get_or_404(entry_id)

    # Verify entry belongs to this list
    if waitlist_entry.list_id != signup_list.id:
        flash("Invalid waitlist entry.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if user has access to this list
    if not signup_list.is_editor(current_user) and not signup_list.user_has_access(
        current_user
    ):
        flash("You do not have access to this list.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Verify user owns this family member OR is an editor
    if waitlist_entry.family_member.user_id != current_user.id and not signup_list.is_editor(current_user):
        flash("You can only remove your own family members from the waitlist.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Get info for logging before deletion
    family_member_name = waitlist_entry.family_member.display_name
    position = waitlist_entry.position
    element_type = waitlist_entry.element_type
    element_id = waitlist_entry.element_id

    # Get element for description
    if element_type == "event":
        element = Event.query.get(element_id)
        if element:
            if element.event_type == "date":
                element_desc = f"event date: {element.event_date.strftime('%B %d, %Y')}"
            else:
                element_desc = f"event datetime: {element.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
        else:
            element_desc = f"event (deleted)"
    else:
        element = Item.query.get(element_id)
        if element:
            element_desc = f"item: {element.name}"
        else:
            element_desc = f"item (deleted)"

    # Delete the waitlist entry
    db.session.delete(waitlist_entry)

    # Log the action
    removed_by = (
        "themselves"
        if waitlist_entry.family_member.user_id == current_user.id
        else f"editor {current_user.email}"
    )
    log_entry = LogEntry(
        project="better_signups",
        category="Remove from Waitlist",
        actor_id=current_user.id,
        description=f"Removed {family_member_name} from waitlist (position #{position}, removed by {removed_by}) on list '{signup_list.name}' (UUID: {signup_list.uuid}), {element_desc}",
    )
    db.session.add(log_entry)

    # Commit
    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while removing from waitlist. Please try again.", "error")
        # Check where to redirect based on 'next' parameter
        next_url = request.form.get("next") or request.args.get("next")
        if next_url and "my-signups" in next_url:
            return redirect(url_for("better_signups.my_signups"))
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    flash(f"Successfully removed {family_member_name} from the waitlist.", "success")

    # Check if we should redirect back to my-signups page
    next_url = request.form.get("next") or request.args.get("next")
    if next_url and "my-signups" in next_url:
        return redirect(url_for("better_signups.my_signups"))

    return redirect(url_for("better_signups.view_list", uuid=uuid))


@bp.route("/lists/<string:uuid>/signup/<int:signup_id>/confirm", methods=["POST"])
@login_required
def confirm_signup(uuid, signup_id):
    """Confirm a pending_confirmation signup"""
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

    # Verify user owns this signup
    if signup.user_id != current_user.id:
        flash("You can only confirm your own signups.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Verify signup is pending_confirmation
    if signup.status != 'pending_confirmation':
        flash("This signup is not pending confirmation.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Check if 24 hours have passed (expired)
    from datetime import timedelta
    if signup.created_at + timedelta(hours=24) < datetime.utcnow():
        flash("This spot offer has expired. It may have been offered to someone else.", "error")
        # Don't redirect yet - let expiration handler clean it up
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Confirm the signup
    signup.status = 'confirmed'
    
    # Get element for logging
    element_desc = ""
    if signup.event_id:
        event = Event.query.get(signup.event_id)
        if event.event_type == "date":
            element_desc = f"event date: {event.event_date.strftime('%B %d, %Y')}"
        else:
            element_desc = f"event datetime: {event.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
    else:
        item = Item.query.get(signup.item_id)
        element_desc = f"item: {item.name}"

    # Log the action
    log_entry = LogEntry(
        project="better_signups",
        category="Confirm Spot",
        actor_id=current_user.id,
        description=f"Confirmed spot for {signup.family_member.display_name} on list '{signup_list.name}' (UUID: {signup_list.uuid}), {element_desc}",
    )
    db.session.add(log_entry)

    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while confirming your spot. Please try again.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    flash(f"Successfully confirmed spot for {signup.family_member.display_name}!", "success")
    return redirect(url_for("better_signups.view_list", uuid=uuid))


@bp.route("/lists/<string:uuid>/signup/<int:signup_id>/decline", methods=["POST"])
@login_required
def decline_signup(uuid, signup_id):
    """Decline a pending_confirmation signup and offer to next person"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    signup = Signup.query.get_or_404(signup_id)

    # Verify signup belongs to an element in this list
    if signup.event_id:
        event = Event.query.get_or_404(signup.event_id)
        if event.list_id != signup_list.id:
            flash("Invalid signup.", "error")
            return redirect(url_for("better_signups.view_list", uuid=uuid))
        element_type = "event"
        element_id = signup.event_id
    elif signup.item_id:
        item = Item.query.get_or_404(signup.item_id)
        if item.list_id != signup_list.id:
            flash("Invalid signup.", "error")
            return redirect(url_for("better_signups.view_list", uuid=uuid))
        element_type = "item"
        element_id = signup.item_id
    else:
        flash("Invalid signup.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Verify user owns this signup
    if signup.user_id != current_user.id:
        flash("You can only decline your own signups.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    # Verify signup is pending_confirmation
    if signup.status != 'pending_confirmation':
        flash("This signup is not pending confirmation.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    family_member_name = signup.family_member.display_name

    # Get element for logging
    element_desc = ""
    if signup.event_id:
        event = Event.query.get(signup.event_id)
        if event.event_type == "date":
            element_desc = f"event date: {event.event_date.strftime('%B %d, %Y')}"
        else:
            element_desc = f"event datetime: {event.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
    else:
        item = Item.query.get(signup.item_id)
        element_desc = f"item: {item.name}"

    # Delete the signup
    db.session.delete(signup)

    # Log the action
    log_entry = LogEntry(
        project="better_signups",
        category="Decline Spot",
        actor_id=current_user.id,
        description=f"Declined spot for {family_member_name} on list '{signup_list.name}' (UUID: {signup_list.uuid}), {element_desc}",
    )
    db.session.add(log_entry)

    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        flash("An error occurred while declining the spot. Please try again.", "error")
        return redirect(url_for("better_signups.view_list", uuid=uuid))

    flash(f"Spot declined for {family_member_name}.", "success")

    # After successful decline, offer to next person on waitlist
    if signup_list.allow_waitlist:
        cascade_result = offer_spot_to_next_in_waitlist(element_type, element_id)
        if cascade_result:
            # Someone else was offered the spot
            logger.info(
                f"Cascade after decline: offered spot to {cascade_result['family_member'].display_name} "
                f"(user {cascade_result['user'].id})"
            )
            # Send email notification
            send_waitlist_offer_email(cascade_result)
            flash(f"The spot has been offered to the next person on the waitlist.", "info")

    return redirect(url_for("better_signups.view_list", uuid=uuid))


@bp.route("/my-signups")
@login_required
def my_signups():
    """View all active signups for the current user and their family members"""
    # Get all family member IDs for current user
    family_member_ids = [
        fm.id for fm in FamilyMember.query.filter_by(user_id=current_user.id).all()
    ]

    if not family_member_ids:
        # No family members yet (shouldn't happen if self is auto-created, but handle it)
        ensure_self_family_member(current_user)
        family_member_ids = [
            fm.id for fm in FamilyMember.query.filter_by(user_id=current_user.id).all()
        ]

    # Get all active signups (not cancelled) for these family members
    # Order by created_at descending (most recent first)
    # Eager load related data to avoid N+1 queries
    signups = (
        Signup.query.options(
            joinedload(Signup.event).joinedload(Event.list),
            joinedload(Signup.item).joinedload(Item.list),
            joinedload(Signup.family_member),
            joinedload(Signup.user),
        )
        .filter(
            Signup.family_member_id.in_(family_member_ids),
        )
        .order_by(Signup.created_at.desc())
        .all()
    )
    
    # Split signups into pending confirmations and confirmed
    from datetime import timedelta
    pending_confirmations = [s for s in signups if s.status == 'pending_confirmation']
    confirmed_signups = [s for s in signups if s.status == 'confirmed']
    
    # Attach deadline info to pending confirmations
    for pending in pending_confirmations:
        pending.deadline = pending.created_at + timedelta(hours=24)
        pending.is_expired = pending.deadline < datetime.utcnow()

    # Get all waitlist entries for these family members
    # Order by created_at descending (most recent first)
    waitlist_entries = (
        WaitlistEntry.query.options(
            joinedload(WaitlistEntry.family_member),
            joinedload(WaitlistEntry.signup_list),
        )
        .filter(WaitlistEntry.family_member_id.in_(family_member_ids))
        .order_by(WaitlistEntry.created_at.desc())
        .all()
    )
    
    # Compute actual current position for each entry
    # (position field may be stale after others are removed)
    for entry in waitlist_entries:
        # Count how many entries are ahead of this one for the same element
        entries_ahead = WaitlistEntry.query.filter_by(
            element_type=entry.element_type,
            element_id=entry.element_id
        ).filter(WaitlistEntry.position < entry.position).count()
        entry.current_position = entries_ahead + 1

    # Generate Google Calendar URLs for all events (date and datetime)
    for signup in confirmed_signups:
        if signup.event:
            list_name = signup.event.list.name
            signup.google_calendar_url = get_google_calendar_url(signup.event, list_name, current_user)
        else:
            signup.google_calendar_url = None

    # Check for existing swap requests for each signup
    # Get all pending swap requests for these family members in these lists
    signup_ids = [s.id for s in confirmed_signups]
    if signup_ids:
        pending_swap_requests = (
            SwapRequest.query.filter(
                SwapRequest.requestor_signup_id.in_(signup_ids),
                SwapRequest.status == "pending"
            )
            .options(
                joinedload(SwapRequest.targets)
            )
            .all()
        )
        # Create a dict mapping signup_id to swap_request
        swap_requests_by_signup = {sr.requestor_signup_id: sr for sr in pending_swap_requests}
    else:
        swap_requests_by_signup = {}

    # Attach swap request info to each signup and check if swap is possible
    for signup in confirmed_signups:
        signup.pending_swap_request = swap_requests_by_signup.get(signup.id)
        
        # If there's a pending swap request, get target element descriptions
        if signup.pending_swap_request:
            signup.swap_target_descriptions = []
            for target in signup.pending_swap_request.targets:
                if target.target_element_type == "event":
                    event = Event.query.get(target.target_element_id)
                    if event:
                        if event.event_type == "date":
                            signup.swap_target_descriptions.append(event.event_date.strftime('%b %d, %Y'))
                        else:
                            signup.swap_target_descriptions.append(event.event_datetime.strftime('%b %d, %I:%M %p'))
                    else:
                        signup.swap_target_descriptions.append("[Deleted]")
                else:
                    item = Item.query.get(target.target_element_id)
                    if item:
                        signup.swap_target_descriptions.append(item.name)
                    else:
                        signup.swap_target_descriptions.append("[Deleted]")
        
        # Check if there are any eligible swap targets for this signup
        # Use helper function instead of inline logic
        signup.has_eligible_swap_targets = check_has_eligible_swap_targets(signup)

    return render_template(
        "better_signups/my_signups.html",
        signups=confirmed_signups,
        pending_confirmations=pending_confirmations,
        waitlist_entries=waitlist_entries,
    )


# ============================================================================
# Phase 12: Swap Request Feature - Placeholder Routes
# ============================================================================

@bp.route("/swap/<int:signup_id>/request", methods=["GET", "POST"])
@login_required
def create_swap_request(signup_id):
    """Create a swap request"""
    # Get the signup with all necessary relationships
    signup = Signup.query.options(
        joinedload(Signup.event).joinedload(Event.list),
        joinedload(Signup.item).joinedload(Item.list),
        joinedload(Signup.family_member),
    ).get_or_404(signup_id)

    # Verify signup belongs to current user
    if signup.user_id != current_user.id:
        flash("You can only create swap requests for your own signups.", "error")
        return redirect(url_for("better_signups.my_signups"))

    # Verify signup is active
    if not signup:
        flash("Signup not found.", "error")
        return redirect(url_for("better_signups.my_signups"))

    # Get the list
    signup_list = signup.event.list if signup.event else signup.item.list

    # Check if this family member already has a pending swap request in this list
    existing_swap_request = SwapRequest.query.filter_by(
        requestor_family_member_id=signup.family_member_id,
        list_id=signup_list.id,
        status="pending"
    ).first()

    if existing_swap_request:
        flash(
            f"You already have a pending swap request in '{signup_list.name}'. "
            "Please cancel it before creating a new one.",
            "error"
        )
        return redirect(url_for("better_signups.my_signups"))

    if request.method == "POST":
        # Get selected target elements
        target_elements_raw = request.form.getlist("target_elements")
        
        if not target_elements_raw:
            flash("Please select at least one element to swap to.", "error")
            return redirect(url_for("better_signups.create_swap_request", signup_id=signup_id))

        if len(target_elements_raw) > 3:
            flash("Maximum 3 target elements allowed.", "error")
            return redirect(url_for("better_signups.create_swap_request", signup_id=signup_id))

        # Parse target elements
        target_elements = []
        for element_str in target_elements_raw:
            try:
                element_type, element_id_str = element_str.split(":", 1)
                element_id = int(element_id_str)
                target_elements.append((element_type, element_id))
            except (ValueError, AttributeError):
                flash("Invalid target element selected.", "error")
                return redirect(url_for("better_signups.create_swap_request", signup_id=signup_id))

        # Validate target elements
        validated_targets = []
        for element_type, element_id in target_elements:
            # Verify element exists and is in same list
            if element_type == "event":
                element = Event.query.get(element_id)
                if not element or element.list_id != signup_list.id:
                    flash(f"Invalid event selected.", "error")
                    return redirect(url_for("better_signups.create_swap_request", signup_id=signup_id))
            elif element_type == "item":
                element = Item.query.get(element_id)
                if not element or element.list_id != signup_list.id:
                    flash(f"Invalid item selected.", "error")
                    return redirect(url_for("better_signups.create_swap_request", signup_id=signup_id))
            else:
                flash(f"Invalid element type.", "error")
                return redirect(url_for("better_signups.create_swap_request", signup_id=signup_id))

            # Verify requestor's family member is NOT already signed up for this target element
            if element_type == "event":
                existing_target_signup = Signup.query.filter_by(
                    event_id=element_id,
                    family_member_id=signup.family_member_id,
                ).first()
            else:
                existing_target_signup = Signup.query.filter_by(
                    item_id=element_id,
                    family_member_id=signup.family_member_id,
                ).first()

            if existing_target_signup:
                flash(
                    f"You are already signed up for one of the selected elements. "
                    "Cannot swap to an element you're already signed up for.",
                    "error"
                )
                return redirect(url_for("better_signups.create_swap_request", signup_id=signup_id))

            validated_targets.append((element_type, element_id, element))

        # Find eligible swap partners across all target elements
        eligible_swap_partners = []  # Will store (recipient_signup, target_element_type, target_element_id) tuples
        
        for element_type, element_id, element in validated_targets:
            # Find all active signups for this target element
            if element_type == "event":
                target_signups = Signup.query.filter_by(
                    event_id=element_id,
                ).options(
                    joinedload(Signup.family_member),
                    joinedload(Signup.user),
                ).all()
            else:
                target_signups = Signup.query.filter_by(
                    item_id=element_id,
                ).options(
                    joinedload(Signup.family_member),
                    joinedload(Signup.user),
                ).all()

            # For each signup on the target element, check if eligible
            for target_signup in target_signups:
                # Skip if same user (though they could have different family members)
                # Actually, we want to allow swaps between different family members of same user
                
                # Check if this family member is already signed up for requestor's element
                requestor_element_id = signup.event_id if signup.event_id else signup.item_id
                requestor_element_type = "event" if signup.event_id else "item"
                
                if requestor_element_type == "event":
                    already_signed_up = Signup.query.filter_by(
                        event_id=requestor_element_id,
                        family_member_id=target_signup.family_member_id,
                    ).first()
                else:
                    already_signed_up = Signup.query.filter_by(
                        item_id=requestor_element_id,
                        family_member_id=target_signup.family_member_id,
                    ).first()

                if not already_signed_up:
                    # This is an eligible swap partner
                    eligible_swap_partners.append((target_signup, element_type, element_id))

        if not eligible_swap_partners:
            flash(
                "No eligible swap partners found for the selected elements. "
                "No one is signed up for these elements who could swap with you.",
                "error"
            )
            return redirect(url_for("better_signups.create_swap_request", signup_id=signup_id))

        # Create swap request
        swap_request = SwapRequest(
            requestor_signup_id=signup.id,
            list_id=signup_list.id,
            requestor_family_member_id=signup.family_member_id,
            status="pending"
        )
        db.session.add(swap_request)
        db.session.flush()  # Get the ID

        # Create SwapRequestTarget records
        for element_type, element_id, element in validated_targets:
            target = SwapRequestTarget(
                swap_request_id=swap_request.id,
                target_element_id=element_id,
                target_element_type=element_type
            )
            db.session.add(target)

        # Create SwapToken records
        for recipient_signup, target_element_type, target_element_id in eligible_swap_partners:
            token = SwapToken(
                swap_request_id=swap_request.id,
                token=SwapToken.generate_token(),
                recipient_signup_id=recipient_signup.id,
                recipient_user_id=recipient_signup.user_id,
                target_element_id=target_element_id,
                target_element_type=target_element_type,
                is_used=False
            )
            db.session.add(token)

        # Log the swap request creation
        target_element_names = []
        for element_type, element_id, element in validated_targets:
            if element_type == "event":
                if element.event_type == "date":
                    target_element_names.append(f"event: {element.event_date.strftime('%B %d, %Y')}")
                else:
                    target_element_names.append(f"event: {element.event_datetime.strftime('%B %d, %Y at %I:%M %p')}")
            else:
                target_element_names.append(f"item: {element.name}")
        
        requestor_element_desc = ""
        if signup.event_id:
            if signup.event.event_type == "date":
                requestor_element_desc = f"event: {signup.event.event_date.strftime('%B %d, %Y')}"
            else:
                requestor_element_desc = f"event: {signup.event.event_datetime.strftime('%B %d, %Y at %I:%M %p')}"
        else:
            requestor_element_desc = f"item: {signup.item.name}"
        
        log_entry = LogEntry(
            project="better_signups",
            category="Create Swap Request",
            actor_id=current_user.id,
            description=f"Created swap request for {signup.family_member.display_name} in list '{signup_list.name}' (UUID: {signup_list.uuid}). "
                       f"Swapping FROM {requestor_element_desc} TO {', '.join(target_element_names)}. "
                       f"Notified {len(set(sp[0].user_id for sp in eligible_swap_partners))} users.",
        )
        db.session.add(log_entry)

        try:
            db.session.commit()
            
            # Send emails to eligible swap partners
            # Group tokens by recipient_user_id
            tokens_by_user = {}
            for token_tuple in eligible_swap_partners:
                recipient_signup, target_element_type, target_element_id = token_tuple
                user_id = recipient_signup.user_id
                
                if user_id not in tokens_by_user:
                    tokens_by_user[user_id] = []
                
                # Find the actual SwapToken object that was created
                token_obj = SwapToken.query.filter_by(
                    swap_request_id=swap_request.id,
                    recipient_signup_id=recipient_signup.id,
                    target_element_id=target_element_id,
                    target_element_type=target_element_type
                ).first()
                
                if token_obj:
                    tokens_by_user[user_id].append(token_obj)
            
            # Send one email per user with all their family's swap options
            emails_sent = 0
            for recipient_user_id, tokens_for_user in tokens_by_user.items():
                recipient_user = User.query.get(recipient_user_id)
                if recipient_user:
                    try:
                        send_swap_request_email(
                            recipient_user=recipient_user,
                            requestor_user=current_user,
                            swap_request=swap_request,
                            tokens_for_recipient=tokens_for_user,
                            list_name=signup_list.name
                        )
                        emails_sent += 1
                    except Exception as e:
                        # Log but continue - we don't want email failures to break swap creation
                        logger.error(f"Failed to send swap email to user {recipient_user_id}: {e}")
            
            if emails_sent > 0:
                flash(
                    f"Swap request created! {emails_sent} user(s) have been notified via email.",
                    "success"
                )
            else:
                flash(
                    f"Swap request created, but emails could not be sent. "
                    "Please check your email configuration.",
                    "warning"
                )
        except SQLAlchemyError as e:
            db.session.rollback()
            flash("An error occurred while creating the swap request. Please try again.", "error")
            return redirect(url_for("better_signups.create_swap_request", signup_id=signup_id))

        return redirect(url_for("better_signups.my_signups"))

    # GET request - show the swap request interface
    # Get all other elements in the same list
    available_elements = []
    
    # Get all events in the list (excluding the one we're swapping from)
    if signup_list.list_type == "events":
        events = Event.query.filter_by(list_id=signup_list.id).options(
            joinedload(Event.signups).joinedload(Signup.family_member),
            joinedload(Event.signups).joinedload(Signup.user),
        ).all()
        for event in events:
            # Skip if this is the event we're swapping from
            if signup.event_id and event.id == signup.event_id:
                continue
            
            # Check if requestor's family member is already signed up for this event
            existing_signup = Signup.query.filter_by(
                event_id=event.id,
                family_member_id=signup.family_member_id,
            ).first()
            
            # Only show elements that are full (no available spots) and have at least one signup
            # If there are available spots, user can just sign up directly - no need to swap
            spots_remaining = event.get_spots_remaining()
            spots_taken = event.get_spots_taken()
            
            if spots_remaining > 0 or spots_taken == 0:
                continue  # Skip this element - either has available spots or no signups
            
            # Get signups for this event
            active_signups = event.get_active_signups()
            signups_info = []
            for s in active_signups:
                signups_info.append({
                    "family_member_name": s.family_member.display_name if s.family_member else s.user.full_name,
                    "user_name": s.user.full_name,
                    "is_self": s.family_member.is_self if s.family_member else False
                })
            
            available_elements.append({
                "id": event.id,
                "type": "event",
                "event": event,
                "item": None,
                "spots_taken": spots_taken,
                "spots_remaining": spots_remaining,
                "is_already_signed_up": existing_signup is not None,
                "signups": signups_info
            })
    
    # Get all items in the list (excluding the one we're swapping from)
    if signup_list.list_type == "items":
        items = Item.query.filter_by(list_id=signup_list.id).options(
            joinedload(Item.signups).joinedload(Signup.family_member),
            joinedload(Item.signups).joinedload(Signup.user),
        ).all()
        for item in items:
            # Skip if this is the item we're swapping from
            if signup.item_id and item.id == signup.item_id:
                continue
            
            # Check if requestor's family member is already signed up for this item
            existing_signup = Signup.query.filter_by(
                item_id=item.id,
                family_member_id=signup.family_member_id,
            ).first()
            
            # Only show elements that are full (no available spots) and have at least one signup
            # If there are available spots, user can just sign up directly - no need to swap
            spots_remaining = item.get_spots_remaining()
            spots_taken = item.get_spots_taken()
            
            if spots_remaining > 0 or spots_taken == 0:
                continue  # Skip this element - either has available spots or no signups
            
            # Get signups for this item
            active_signups = item.get_active_signups()
            signups_info = []
            for s in active_signups:
                signups_info.append({
                    "family_member_name": s.family_member.display_name if s.family_member else s.user.full_name,
                    "user_name": s.user.full_name,
                    "is_self": s.family_member.is_self if s.family_member else False
                })
            
            available_elements.append({
                "id": item.id,
                "type": "item",
                "event": None,
                "item": item,
                "spots_taken": spots_taken,
                "spots_remaining": spots_remaining,
                "is_already_signed_up": existing_signup is not None,
                "signups": signups_info
            })

    return render_template(
        "better_signups/create_swap_request.html",
        signup=signup,
        signup_list=signup_list,
        available_elements=available_elements
    )


@bp.route("/swap/<int:swap_request_id>/cancel", methods=["POST"])
@login_required
def cancel_swap_request(swap_request_id):
    """Cancel a swap request"""
    swap_request = SwapRequest.query.get_or_404(swap_request_id)
    
    # Verify swap request belongs to current user
    if swap_request.requestor_signup and swap_request.requestor_signup.user_id != current_user.id:
        flash("You can only cancel your own swap requests.", "error")
        return redirect(url_for("better_signups.my_signups"))
    
    # Check if already completed or cancelled
    if swap_request.status != "pending":
        flash(f"This swap request is already {swap_request.status}.", "info")
        return redirect(url_for("better_signups.my_signups"))
    
    # Mark as cancelled
    swap_request.status = "cancelled"
    
    # Invalidate all associated tokens
    for token in swap_request.tokens:
        if not token.is_used:
            token.is_used = True
            token.used_at = datetime.utcnow()
    
    # Log the cancellation
    log_entry = LogEntry(
        project="better_signups",
        category="Cancel Swap Request",
        actor_id=current_user.id,
        description=f"Cancelled swap request (ID: {swap_request_id}) in list '{swap_request.list.name}'",
    )
    db.session.add(log_entry)
    
    try:
        db.session.commit()
        flash("Swap request cancelled successfully.", "success")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error cancelling swap request: {e}")
        flash("An error occurred while cancelling the swap request.", "error")
    
    return redirect(url_for("better_signups.my_signups"))


@bp.route("/swap/execute/<string:token>", methods=["GET"])
def execute_swap(token):
    """Execute a swap via token link"""
    # Get the token
    swap_token = SwapToken.query.filter_by(token=token).first()
    
    if not swap_token:
        return render_template(
            "better_signups/swap_error.html",
            error_title="Invalid Swap Link",
            error_message="This swap link is invalid or has expired.",
        )
    
    # Check if token is already used
    if swap_token.is_used:
        return render_template(
            "better_signups/swap_error.html",
            error_title="Swap Already Completed",
            error_message="This swap has already been completed. The link can only be used once.",
        )
    
    # Get the swap request
    swap_request = swap_token.swap_request
    
    # Check if swap request is still pending
    if swap_request.status != "pending":
        status_msg = {
            "completed": "This swap request has already been completed.",
            "cancelled": "This swap request has been cancelled.",
        }.get(swap_request.status, "This swap request is no longer active.")
        
        return render_template(
            "better_signups/swap_error.html",
            error_title="Swap Not Available",
            error_message=status_msg,
        )
    
    # Get both signups
    requestor_signup = swap_request.requestor_signup
    recipient_signup = swap_token.recipient_signup
    
    # Verify both signups still exist (not deleted)
    if not requestor_signup or not recipient_signup:
        return render_template(
            "better_signups/swap_error.html",
            error_title="Signup Not Found",
            error_message="One of the signups involved in this swap no longer exists.",
        )
    
    # Verify target element still exists in swap request targets
    target_exists = any(
        t.target_element_id == swap_token.target_element_id 
        and t.target_element_type == swap_token.target_element_type
        for t in swap_request.targets
    )
    
    if not target_exists:
        return render_template(
            "better_signups/swap_error.html",
            error_title="Target Element Removed",
            error_message="The element you wanted to swap to is no longer available in this swap request.",
        )
    
    # Get the target element
    if swap_token.target_element_type == "event":
        target_element = Event.query.get(swap_token.target_element_id)
    else:
        target_element = Item.query.get(swap_token.target_element_id)
    
    if not target_element:
        return render_template(
            "better_signups/swap_error.html",
            error_title="Element Deleted",
            error_message="The element you wanted to swap to has been deleted from the list.",
        )
    
    # Get requestor's element
    if requestor_signup.event_id:
        requestor_element = Event.query.get(requestor_signup.event_id)
        requestor_element_type = "event"
    else:
        requestor_element = Item.query.get(requestor_signup.item_id)
        requestor_element_type = "item"
    
    if not requestor_element:
        return render_template(
            "better_signups/swap_error.html",
            error_title="Element Deleted",
            error_message="The element being swapped from has been deleted from the list.",
        )
    
    # Get list
    signup_list = swap_request.list
    
    # Execute the swap atomically
    try:
        # Create new signups
        # Requestor's family member → target element
        new_requestor_signup = Signup(
            user_id=requestor_signup.user_id,
            family_member_id=requestor_signup.family_member_id,
        )
        if swap_token.target_element_type == "event":
            new_requestor_signup.event_id = swap_token.target_element_id
        else:
            new_requestor_signup.item_id = swap_token.target_element_id
        
        # Recipient's family member → requestor's original element
        new_recipient_signup = Signup(
            user_id=recipient_signup.user_id,
            family_member_id=recipient_signup.family_member_id,
        )
        if requestor_element_type == "event":
            new_recipient_signup.event_id = requestor_element.id
        else:
            new_recipient_signup.item_id = requestor_element.id
        
        # Mark swap request as completed FIRST (before deleting signups)
        # This is important because requestor_signup_id has a foreign key constraint
        swap_request.status = "completed"
        swap_request.completed_at = datetime.utcnow()
        swap_request.completed_by_user_id = swap_token.recipient_user_id
        
        # Delete old signups
        db.session.delete(requestor_signup)
        db.session.delete(recipient_signup)
        
        # Add new signups
        db.session.add(new_requestor_signup)
        db.session.add(new_recipient_signup)
        
        # Mark token as used
        swap_token.mark_as_used()
        
        # Invalidate all other tokens for this swap request
        for other_token in swap_request.tokens:
            if other_token.id != swap_token.id and not other_token.is_used:
                other_token.is_used = True
                other_token.used_at = datetime.utcnow()
        
        # Log the swap execution
        requestor_family_member = swap_request.requestor_family_member
        recipient_family_member = recipient_signup.family_member
        
        # Get element descriptions for logging
        if requestor_element_type == "event":
            if requestor_element.event_type == "date":
                requestor_element_desc = requestor_element.event_date.strftime('%B %d, %Y')
            else:
                requestor_element_desc = requestor_element.event_datetime.strftime('%B %d, %Y at %I:%M %p')
        else:
            requestor_element_desc = requestor_element.name
        
        if swap_token.target_element_type == "event":
            if target_element.event_type == "date":
                target_element_desc = target_element.event_date.strftime('%B %d, %Y')
            else:
                target_element_desc = target_element.event_datetime.strftime('%B %d, %Y at %I:%M %p')
        else:
            target_element_desc = target_element.name
        
        log_entry = LogEntry(
            project="better_signups",
            category="Execute Swap",
            actor_id=swap_token.recipient_user_id,
            description=f"Swap executed in list '{signup_list.name}' (UUID: {signup_list.uuid}). "
                       f"{requestor_family_member.display_name} swapped from '{requestor_element_desc}' to '{target_element_desc}'. "
                       f"{recipient_family_member.display_name} swapped from '{target_element_desc}' to '{requestor_element_desc}'.",
        )
        db.session.add(log_entry)
        
        # Commit the transaction
        db.session.commit()
        
        # Send completion emails (after commit, so we don't send if transaction fails)
        requestor_user = User.query.get(requestor_signup.user_id)
        recipient_user = User.query.get(swap_token.recipient_user_id)
        
        if requestor_user and recipient_user:
            from app.utils.email_service import send_email
            
            # Email to requestor
            try:
                requestor_subject = f"Swap Completed in '{signup_list.name}'"
                requestor_text = f"""Hello {requestor_user.full_name},

Good news! Your swap request in '{signup_list.name}' has been completed.

{requestor_family_member.display_name} has been swapped:
- FROM: {requestor_element_desc}
- TO: {target_element_desc}

{recipient_user.full_name} accepted your swap request.

You can view your updated signups at: {url_for('better_signups.my_signups', _external=True)}

Best regards,
gregmichnikov.com
"""
                requestor_html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .success-box {{ background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #28a745; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>✅ Swap Completed!</h2>
        <p>Hello {requestor_user.full_name},</p>
        <p>Good news! Your swap request in <strong>'{signup_list.name}'</strong> has been completed.</p>
        
        <div class="success-box">
            <p style="margin: 0 0 10px 0; font-weight: bold;">{requestor_family_member.display_name} has been swapped:</p>
            <p style="margin: 0;">✗ FROM: <span style="text-decoration: line-through;">{requestor_element_desc}</span></p>
            <p style="margin: 0;">✓ TO: <strong style="color: #28a745;">{target_element_desc}</strong></p>
        </div>
        
        <p><strong>{recipient_user.full_name}</strong> accepted your swap request.</p>
        
        <p>
            <a href="{url_for('better_signups.my_signups', _external=True)}" 
               style="display: inline-block; padding: 12px 24px; background-color: #007bff; color: #ffffff !important; text-decoration: none; border-radius: 5px; font-weight: bold;">
                View My Signups
            </a>
        </p>
        
        <div class="footer">
            <p>Best regards,<br>gregmichnikov.com</p>
        </div>
    </div>
</body>
</html>
"""
                send_email(requestor_user.email, requestor_subject, requestor_text, requestor_html)
            except Exception as e:
                logger.error(f"Failed to send swap completion email to requestor {requestor_user.email}: {e}")
            
            # Email to recipient
            try:
                recipient_subject = f"Swap Completed in '{signup_list.name}'"
                recipient_text = f"""Hello {recipient_user.full_name},

You have successfully completed a swap in '{signup_list.name}'.

{recipient_family_member.display_name} has been swapped:
- FROM: {target_element_desc}
- TO: {requestor_element_desc}

The swap was with {requestor_user.full_name}.

You can view your updated signups at: {url_for('better_signups.my_signups', _external=True)}

Best regards,
gregmichnikov.com
"""
                recipient_html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .success-box {{ background-color: #d4edda; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #28a745; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>✅ Swap Completed!</h2>
        <p>Hello {recipient_user.full_name},</p>
        <p>You have successfully completed a swap in <strong>'{signup_list.name}'</strong>.</p>
        
        <div class="success-box">
            <p style="margin: 0 0 10px 0; font-weight: bold;">{recipient_family_member.display_name} has been swapped:</p>
            <p style="margin: 0;">✗ FROM: <span style="text-decoration: line-through;">{target_element_desc}</span></p>
            <p style="margin: 0;">✓ TO: <strong style="color: #28a745;">{requestor_element_desc}</strong></p>
        </div>
        
        <p>The swap was with <strong>{requestor_user.full_name}</strong>.</p>
        
        <p>
            <a href="{url_for('better_signups.my_signups', _external=True)}" 
               style="display: inline-block; padding: 12px 24px; background-color: #007bff; color: #ffffff !important; text-decoration: none; border-radius: 5px; font-weight: bold;">
                View My Signups
            </a>
        </p>
        
        <div class="footer">
            <p>Best regards,<br>gregmichnikov.com</p>
        </div>
    </div>
</body>
</html>
"""
                send_email(recipient_user.email, recipient_subject, recipient_text, recipient_html)
            except Exception as e:
                logger.error(f"Failed to send swap completion email to recipient {recipient_user.email}: {e}")
        
        # Show success page
        return render_template(
            "better_signups/swap_success.html",
            swap_request=swap_request,
            requestor_family_member=requestor_family_member,
            recipient_family_member=recipient_family_member,
            requestor_element_desc=requestor_element_desc,
            target_element_desc=target_element_desc,
            signup_list=signup_list,
        )
        
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"IntegrityError during swap execution: {e}")
        return render_template(
            "better_signups/swap_error.html",
            error_title="Swap Failed",
            error_message="The swap could not be completed. One of the family members may already be signed up for the target element.",
        )
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error executing swap: {e}")
        return render_template(
            "better_signups/swap_error.html",
            error_title="Swap Failed",
            error_message="An unexpected error occurred while completing the swap. Please try again or contact support.",
        )

