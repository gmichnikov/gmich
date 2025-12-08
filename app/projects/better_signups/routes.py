"""
Better Signups - Routes
Handles signup list creation, management, and signups
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.forms import FamilyMemberForm
from app.projects.better_signups.models import FamilyMember

bp = Blueprint('better_signups', __name__,
               url_prefix='/better-signups',
               template_folder='templates',
               static_folder='static')


@bp.route('/')
@login_required
def index():
    """Main Better Signups page"""
    return render_template('better_signups/index.html')


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

