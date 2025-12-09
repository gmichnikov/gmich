"""
Better Signups - Routes
Handles signup list creation, management, and signups
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import or_
from app import db
from app.forms import FamilyMemberForm, CreateSignupListForm, EditSignupListForm, AddListEditorForm
from app.projects.better_signups.models import FamilyMember, SignupList, ListEditor
from app.models import User

bp = Blueprint('better_signups', __name__,
               url_prefix='/better-signups',
               template_folder='templates',
               static_folder='static')


@bp.route('/')
@login_required
def index():
    """Main Better Signups page"""
    # Get lists created by current user
    my_lists = SignupList.query.filter_by(creator_id=current_user.id).order_by(
        SignupList.created_at.desc()
    ).all()
    
    # Get lists where user is an editor (but not creator)
    # This includes lists where user_id matches, or email matches (for pending invitations)
    editor_lists = SignupList.query.join(ListEditor).filter(
        SignupList.creator_id != current_user.id,
        or_(
            ListEditor.user_id == current_user.id,
            ListEditor.email == current_user.email.lower()
        )
    ).order_by(SignupList.created_at.desc()).all()
    
    return render_template('better_signups/index.html', my_lists=my_lists, editor_lists=editor_lists)


@bp.route('/family-members')
@login_required
def family_members():
    """View and manage family members"""
    # Ensure "self" family member exists
    from app.projects.better_signups.utils import ensure_self_family_member
    ensure_self_family_member(current_user)
    
    form = FamilyMemberForm()
    family_members_list = FamilyMember.query.filter_by(user_id=current_user.id).order_by(
        FamilyMember.is_self.desc(), FamilyMember.created_at
    ).all()
    
    return render_template(
        'better_signups/family_members.html',
        form=form,
        family_members=family_members_list
    )


@bp.route('/family-members/add', methods=['POST'])
@login_required
def add_family_member():
    """Add a new family member"""
    form = FamilyMemberForm()
    
    if form.validate_on_submit():
        # Check if user already has a "self" family member
        # (This shouldn't happen if auto-creation works, but just in case)
        existing_self = FamilyMember.query.filter_by(
            user_id=current_user.id,
            is_self=True
        ).first()
        
        if not existing_self:
            # Create "self" family member if it doesn't exist
            self_member = FamilyMember(
                user_id=current_user.id,
                display_name=current_user.full_name,
                is_self=True
            )
            db.session.add(self_member)
        
        # Create new family member
        family_member = FamilyMember(
            user_id=current_user.id,
            display_name=form.display_name.data.strip(),
            is_self=False
        )
        db.session.add(family_member)
        db.session.commit()
        
        flash(f'Family member "{family_member.display_name}" added successfully.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')
    
    return redirect(url_for('better_signups.family_members'))


@bp.route('/family-members/<int:member_id>/delete', methods=['POST'])
@login_required
def delete_family_member(member_id):
    """Delete a family member"""
    family_member = FamilyMember.query.get_or_404(member_id)
    
    # Verify the family member belongs to the current user
    if family_member.user_id != current_user.id:
        flash('You do not have permission to delete this family member.', 'error')
        return redirect(url_for('better_signups.family_members'))
    
    # Prevent deletion of "self" family member
    if family_member.is_self:
        flash('You cannot delete your own family member record.', 'error')
        return redirect(url_for('better_signups.family_members'))
    
    # Check if there are any active signups for this family member
    active_signups = [s for s in family_member.signups if s.cancelled_at is None]
    if active_signups:
        flash(
            f'Cannot delete "{family_member.display_name}" because they have active signups. '
            'Please cancel all signups first.',
            'error'
        )
        return redirect(url_for('better_signups.family_members'))
    
    name = family_member.display_name
    db.session.delete(family_member)
    db.session.commit()
    
    flash(f'Family member "{name}" deleted successfully.', 'success')
    return redirect(url_for('better_signups.family_members'))


@bp.route('/lists/create', methods=['GET', 'POST'])
@login_required
def create_list():
    """Create a new signup list"""
    form = CreateSignupListForm()
    
    if form.validate_on_submit():
        # Create new list
        new_list = SignupList(
            name=form.name.data.strip(),
            description=form.description.data.strip() if form.description.data else None,
            list_type=form.list_type.data,
            creator_id=current_user.id,
            accepting_signups=True
        )
        
        # Generate UUID
        new_list.generate_uuid()
        
        # Set password if provided
        if form.list_password.data and form.list_password.data.strip():
            new_list.set_list_password(form.list_password.data)
        
        db.session.add(new_list)
        db.session.commit()
        
        flash(f'List "{new_list.name}" created successfully!', 'success')
        return redirect(url_for('better_signups.view_list', uuid=new_list.uuid))
    
    return render_template('better_signups/create_list.html', form=form)


@bp.route('/lists/<string:uuid>')
@login_required
def view_list(uuid):
    """View and edit a signup list (editor view)"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    
    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash('You do not have permission to view this list.', 'error')
        return redirect(url_for('better_signups.index'))
    
    form = EditSignupListForm(obj=signup_list)
    form.accepting_signups.data = signup_list.accepting_signups
    
    # Form for adding editors (only shown to creator)
    add_editor_form = AddListEditorForm() if signup_list.creator_id == current_user.id else None
    
    # Get list of editors (excluding creator)
    editors = ListEditor.query.filter_by(list_id=signup_list.id).all()
    
    return render_template(
        'better_signups/view_list.html', 
        list=signup_list, 
        form=form,
        add_editor_form=add_editor_form,
        editors=editors
    )


@bp.route('/lists/<string:uuid>/edit', methods=['POST'])
@login_required
def edit_list(uuid):
    """Edit a signup list"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    
    # Check if user is an editor
    if not signup_list.is_editor(current_user):
        flash('You do not have permission to edit this list.', 'error')
        return redirect(url_for('better_signups.index'))
    
    form = EditSignupListForm()
    
    if form.validate_on_submit():
        signup_list.name = form.name.data.strip()
        signup_list.description = form.description.data.strip() if form.description.data else None
        signup_list.accepting_signups = form.accepting_signups.data
        
        # Update password if provided
        if form.list_password.data and form.list_password.data.strip():
            signup_list.set_list_password(form.list_password.data)
        
        db.session.commit()
        
        flash(f'List "{signup_list.name}" updated successfully!', 'success')
        return redirect(url_for('better_signups.view_list', uuid=signup_list.uuid))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')
        return redirect(url_for('better_signups.view_list', uuid=signup_list.uuid))


@bp.route('/lists/<string:uuid>/delete', methods=['POST'])
@login_required
def delete_list(uuid):
    """Delete a signup list"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    
    # Only creator can delete
    if signup_list.creator_id != current_user.id:
        flash('Only the list creator can delete this list.', 'error')
        return redirect(url_for('better_signups.index'))
    
    # Check if there are any signups
    from app.projects.better_signups.models import Signup, Event, Item
    event_ids = [e.id for e in signup_list.events]
    item_ids = [i.id for i in signup_list.items]
    
    has_signups = False
    if event_ids:
        has_signups = db.session.query(Signup).filter(Signup.event_id.in_(event_ids)).first() is not None
    if not has_signups and item_ids:
        has_signups = db.session.query(Signup).filter(Signup.item_id.in_(item_ids)).first() is not None
    
    if has_signups:
        flash('Cannot delete a list that has signups. Please remove all signups first.', 'error')
        return redirect(url_for('better_signups.view_list', uuid=signup_list.uuid))
    
    name = signup_list.name
    db.session.delete(signup_list)
    db.session.commit()
    
    flash(f'List "{name}" deleted successfully.', 'success')
    return redirect(url_for('better_signups.index'))


@bp.route('/lists/<string:uuid>/editors/add', methods=['POST'])
@login_required
def add_editor(uuid):
    """Add an editor to a signup list"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    
    # Only creator can add editors
    if signup_list.creator_id != current_user.id:
        flash('Only the list creator can add editors.', 'error')
        return redirect(url_for('better_signups.view_list', uuid=signup_list.uuid))
    
    form = AddListEditorForm()
    
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        
        # Try to find user by email
        user = User.query.filter_by(email=email).first()
        
        # Check if user is already an editor (or is the creator)
        if user and user.id == signup_list.creator_id:
            flash('The list creator is already an editor.', 'error')
            return redirect(url_for('better_signups.view_list', uuid=signup_list.uuid))
        
        # Check if already an editor (by user_id or by email)
        existing_editor = None
        if user:
            existing_editor = ListEditor.query.filter_by(
                list_id=signup_list.id,
                user_id=user.id
            ).first()
        else:
            existing_editor = ListEditor.query.filter_by(
                list_id=signup_list.id,
                email=email
            ).first()
        
        if existing_editor:
            flash('This email is already an editor.', 'error')
            return redirect(url_for('better_signups.view_list', uuid=signup_list.uuid))
        
        # Add as editor (with user_id if user exists, otherwise just email)
        editor = ListEditor(
            list_id=signup_list.id,
            user_id=user.id if user else None,
            email=email
        )
        db.session.add(editor)
        db.session.commit()
        
        # Generic success message to avoid email enumeration
        flash(f'Editor added successfully. {email} can now edit this list.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{field}: {error}', 'error')
    
    return redirect(url_for('better_signups.view_list', uuid=signup_list.uuid))


@bp.route('/lists/<string:uuid>/editors/<int:editor_id>/remove', methods=['POST'])
@login_required
def remove_editor(uuid, editor_id):
    """Remove an editor from a signup list"""
    signup_list = SignupList.query.filter_by(uuid=uuid).first_or_404()
    
    # Only creator can remove editors
    if signup_list.creator_id != current_user.id:
        flash('Only the list creator can remove editors.', 'error')
        return redirect(url_for('better_signups.view_list', uuid=signup_list.uuid))
    
    editor = ListEditor.query.get_or_404(editor_id)
    
    # Verify the editor belongs to this list
    if editor.list_id != signup_list.id:
        flash('Invalid editor.', 'error')
        return redirect(url_for('better_signups.view_list', uuid=signup_list.uuid))
    
    # Get editor info before deletion
    editor_email = editor.get_display_email() or 'Unknown'
    
    db.session.delete(editor)
    db.session.commit()
    
    # Generic message to avoid revealing whether user has an account
    flash(f'Editor {editor_email} removed successfully.', 'success')
    return redirect(url_for('better_signups.view_list', uuid=signup_list.uuid))

