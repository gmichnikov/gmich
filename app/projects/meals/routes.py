from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models import User
from app.projects.meals.models import MealsFamilyGroup, MealsFamilyMember
from app.projects.meals.forms import CreateFamilyGroupForm, InviteMemberForm, AddGuestMemberForm
from app.projects.meals.utils import get_user_family_groups, is_user_in_group

meals_bp = Blueprint('meals', __name__, 
                    url_prefix='/meals',
                    template_folder='templates',
                    static_folder='static')

@meals_bp.route('/')
@login_required
def index():
    groups = get_user_family_groups(current_user)
    create_form = CreateFamilyGroupForm()
    return render_template('meals/index.html', groups=groups, create_form=create_form)

@meals_bp.route('/groups/create', methods=['POST'])
@login_required
def create_group():
    form = CreateFamilyGroupForm()
    if form.validate_on_submit():
        group = MealsFamilyGroup(name=form.name.data)
        db.session.add(group)
        db.session.flush() # Get the group ID
        
        # Add current user as the first member
        member = MealsFamilyMember(
            family_group_id=group.id,
            user_id=current_user.id,
            display_name=current_user.short_name
        )
        db.session.add(member)
        db.session.commit()
        
        flash(f'Family group "{group.name}" created!', 'success')
    return redirect(url_for('meals.index'))

@meals_bp.route('/groups/<int:group_id>/invite', methods=['GET', 'POST'])
@login_required
def invite_member(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
        
    group = MealsFamilyGroup.query.get_or_404(group_id)
    form = InviteMemberForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            flash(f'User with email {form.email.data} not found.', 'danger')
        else:
            # Check if already a member
            existing = MealsFamilyMember.query.filter_by(
                family_group_id=group_id,
                user_id=user.id
            ).first()
            
            if existing:
                flash(f'{user.full_name} is already a member of this group.', 'info')
            else:
                member = MealsFamilyMember(
                    family_group_id=group_id,
                    user_id=user.id,
                    display_name=user.short_name
                )
                db.session.add(member)
                db.session.commit()
                flash(f'Invited {user.full_name} to the group.', 'success')
        return redirect(url_for('meals.group_detail', group_id=group_id))
        
    return render_template('meals/invite.html', group=group, form=form)

@meals_bp.route('/groups/<int:group_id>/members/add', methods=['GET', 'POST'])
@login_required
def add_guest_member(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
        
    group = MealsFamilyGroup.query.get_or_404(group_id)
    form = AddGuestMemberForm()
    
    if form.validate_on_submit():
        member = MealsFamilyMember(
            family_group_id=group_id,
            display_name=form.display_name.data
        )
        db.session.add(member)
        db.session.commit()
        flash(f'Added guest member {form.display_name.data}.', 'success')
        return redirect(url_for('meals.group_detail', group_id=group_id))
        
    return render_template('meals/add_guest.html', group=group, form=form)

@meals_bp.route('/groups/<int:group_id>')
@login_required
def group_detail(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
        
    group = MealsFamilyGroup.query.get_or_404(group_id)
    invite_form = InviteMemberForm()
    guest_form = AddGuestMemberForm()
    return render_template('meals/group_detail.html', 
                           group=group, 
                           invite_form=invite_form, 
                           guest_form=guest_form)
