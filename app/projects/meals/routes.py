from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from sqlalchemy import func
from flask_login import login_required, current_user
import calendar
import pytz
from datetime import date, timedelta, datetime
from app import db
from app.models import User
from app.projects.meals.models import MealsFamilyGroup, MealsFamilyMember, MealsEntry
from app.projects.meals.forms import CreateFamilyGroupForm, InviteMemberForm, AddGuestMemberForm, LogMealForm, EditEntryForm
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

@meals_bp.route('/groups/<int:group_id>')
@login_required
def group_detail(group_id):
    """Default view for a group, redirects to logging a meal."""
    if not is_user_in_group(current_user, group_id):
        abort(404)
    return redirect(url_for('meals.log_meal_view', group_id=group_id))

@meals_bp.route('/groups/<int:group_id>/log', methods=['GET'])
@login_required
def log_meal_view(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
    group = MealsFamilyGroup.query.get_or_404(group_id)
    
    # Get user's local date for the log form default
    user_tz = pytz.timezone(current_user.time_zone)
    user_now = datetime.now(user_tz)
    
    log_form = LogMealForm()
    
    # Pre-populate from query parameters
    pre_date = request.args.get('date')
    pre_meal = request.args.get('meal_type')
    pre_members = request.args.getlist('member_id', type=int)
    
    if pre_date:
        try:
            log_form.date.data = datetime.strptime(pre_date, '%Y-%m-%d').date()
        except ValueError:
            log_form.date.data = user_now.date()
    else:
        log_form.date.data = user_now.date()
        
    if pre_meal:
        log_form.meal_type.data = pre_meal
        
    log_form.member_ids.choices = [(m.id, m.name) for m in group.members]
    if pre_members:
        log_form.member_ids.data = pre_members
    
    return render_template('meals/tabs/log.html', group=group, log_form=log_form, active_tab='log')

@meals_bp.route('/groups/<int:group_id>/log', methods=['POST'])
@login_required
def log_meal(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
    
    group = MealsFamilyGroup.query.get_or_404(group_id)
    form = LogMealForm()
    form.member_ids.choices = [(m.id, m.display_name) for m in group.members]
    
    if form.validate_on_submit():
        for member_id in form.member_ids.data:
            entry = MealsEntry(
                family_group_id=group_id,
                member_id=member_id,
                food_name=form.food_name.data,
                location=form.location.data,
                meal_type=form.meal_type.data,
                date=form.date.data,
                created_by_id=current_user.id
            )
            db.session.add(entry)
        
        db.session.commit()
        flash(f'Logged {form.meal_type.data} for {len(form.member_ids.data)} members!', 'success')
        return redirect(url_for('meals.log_meal_view', group_id=group_id))
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error in {field}: {error}', 'danger')
                
    return redirect(url_for('meals.log_meal_view', group_id=group_id))

@meals_bp.route('/groups/<int:group_id>/history')
@login_required
def history_view(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
    group = MealsFamilyGroup.query.get_or_404(group_id)
    recent_entries = MealsEntry.query.filter_by(family_group_id=group_id).order_by(MealsEntry.date.desc(), MealsEntry.created_at.desc()).limit(50).all()
    return render_template('meals/tabs/history.html', group=group, recent_entries=recent_entries, active_tab='history')

@meals_bp.route('/groups/<int:group_id>/stats')
@login_required
def stats_view(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
    group = MealsFamilyGroup.query.get_or_404(group_id)
    
    member_filter = request.args.get('member_id', type=int)
    common_query = db.session.query(
        MealsEntry.food_name, 
        MealsEntry.location, 
        func.count(MealsEntry.id).label('count')
    ).filter(MealsEntry.family_group_id == group_id)
    
    if member_filter:
        common_query = common_query.filter(MealsEntry.member_id == member_filter)
    
    common_meals = common_query.group_by(
        MealsEntry.food_name, 
        MealsEntry.location
    ).order_by(func.count(MealsEntry.id).desc()).limit(20).all()
    
    # Location Trends (Home vs Out)
    home_count = MealsEntry.query.filter(
        MealsEntry.family_group_id == group_id,
        MealsEntry.location.ilike('home')
    ).count()
    
    total_with_location = MealsEntry.query.filter(
        MealsEntry.family_group_id == group_id,
        MealsEntry.location.isnot(None),
        MealsEntry.location != ''
    ).count()
    
    out_count = total_with_location - home_count
    
    return render_template('meals/tabs/stats.html', 
                           group=group, 
                           common_meals=common_meals,
                           home_count=home_count,
                           out_count=out_count,
                           member_filter=member_filter,
                           active_tab='stats')

@meals_bp.route('/groups/<int:group_id>/family')
@login_required
def family_view(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
    group = MealsFamilyGroup.query.get_or_404(group_id)
    invite_form = InviteMemberForm()
    guest_form = AddGuestMemberForm()
    return render_template('meals/tabs/family.html', 
                           group=group, 
                           invite_form=invite_form, 
                           guest_form=guest_form,
                           active_tab='family')

@meals_bp.route('/groups/<int:group_id>/invite', methods=['POST'])
@login_required
def invite_member(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
    form = InviteMemberForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            flash(f'User with email {form.email.data} not found.', 'danger')
        else:
            existing = MealsFamilyMember.query.filter_by(family_group_id=group_id, user_id=user.id).first()
            if existing:
                flash(f'{user.full_name} is already a member.', 'info')
            else:
                member = MealsFamilyMember(family_group_id=group_id, user_id=user.id, display_name=user.short_name)
                db.session.add(member)
                db.session.commit()
                flash(f'Invited {user.full_name}.', 'success')
    return redirect(url_for('meals.family_view', group_id=group_id))

@meals_bp.route('/groups/<int:group_id>/members/add', methods=['POST'])
@login_required
def add_guest_member(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
    form = AddGuestMemberForm()
    if form.validate_on_submit():
        member = MealsFamilyMember(family_group_id=group_id, display_name=form.display_name.data)
        db.session.add(member)
        db.session.commit()
        flash(f'Added guest member {form.display_name.data}.', 'success')
    return redirect(url_for('meals.family_view', group_id=group_id))

@meals_bp.route('/groups/<int:group_id>/calendar')
@login_required
def calendar_view(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
        
    group = MealsFamilyGroup.query.get_or_404(group_id)
    view_type = request.args.get('view', 'monthly') # 'monthly', 'weekly', or 'daily'
    
    # Get user's local date for defaults
    user_tz = pytz.timezone(current_user.time_zone)
    user_today = datetime.now(user_tz).date()
    
    # Get current date or date from params
    year = request.args.get('year', user_today.year, type=int)
    month = request.args.get('month', user_today.month, type=int)
    day = request.args.get('day', user_today.day, type=int)
    member_filter = request.args.get('member_id', type=int)
    
    current_focus = date(year, month, day)
    
    if view_type == 'monthly':
        start_date = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        end_date = date(year, month, last_day)
        start_date = start_date - timedelta(days=(start_date.weekday() + 1) % 7)
        end_date = end_date + timedelta(days=(5 - end_date.weekday() + 1) % 7)
        prev_date = (date(year, month, 1) - timedelta(days=1))
        next_date = (date(year, month, 1) + timedelta(days=32)).replace(day=1)
    elif view_type == 'weekly':
        start_date = current_focus - timedelta(days=(current_focus.weekday() + 1) % 7)
        end_date = start_date + timedelta(days=6)
        prev_date = start_date - timedelta(days=7)
        next_date = start_date + timedelta(days=7)
    else: # daily
        start_date = current_focus
        end_date = current_focus
        prev_date = current_focus - timedelta(days=1)
        next_date = current_focus + timedelta(days=1)

    query = MealsEntry.query.filter(
        MealsEntry.family_group_id == group_id,
        MealsEntry.date >= start_date,
        MealsEntry.date <= end_date
    )
    if member_filter:
        query = query.filter(MealsEntry.member_id == member_filter)
    entries = query.order_by(MealsEntry.date, MealsEntry.meal_type).all()
    
    calendar_data = {}
    curr = start_date
    while curr <= end_date:
        calendar_data[curr] = {'Breakfast': {}, 'Lunch': {}, 'Dinner': {}}
        curr += timedelta(days=1)
        
    for entry in entries:
        if entry.date in calendar_data:
            meal_key = f"{entry.food_name}|{entry.location or ''}"
            if meal_key not in calendar_data[entry.date][entry.meal_type]:
                calendar_data[entry.date][entry.meal_type][meal_key] = []
            calendar_data[entry.date][entry.meal_type][meal_key].append(entry)

    # For daily view, we need a flat structure of member entries
    daily_matrix = {} # {member_id: {meal_type: [entries]}}
    if view_type == 'daily':
        for member in group.members:
            daily_matrix[member.id] = {'Breakfast': [], 'Lunch': [], 'Dinner': []}
        for entry in entries:
            daily_matrix[entry.member_id][entry.meal_type].append(entry)

    return render_template('meals/calendar.html',
                           group=group,
                           view_type=view_type,
                           calendar_data=calendar_data,
                           daily_matrix=daily_matrix,
                           start_date=start_date,
                           end_date=end_date,
                           current_focus=current_focus,
                           prev_date=prev_date,
                           next_date=next_date,
                           month_name=calendar.month_name[month],
                           year=year,
                           today=user_today,
                           member_filter=member_filter,
                           active_tab='calendar')

@meals_bp.route('/groups/<int:group_id>/entries/<int:entry_id>/edit', methods=['GET'])
@login_required
def edit_entry_view(group_id, entry_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
    group = MealsFamilyGroup.query.get_or_404(group_id)
    entry = MealsEntry.query.get_or_404(entry_id)
    if entry.family_group_id != group_id:
        abort(404)
    edit_form = EditEntryForm()
    edit_form.member_ids.choices = [(m.id, m.name) for m in group.members]
    edit_form.date.data = entry.date
    edit_form.meal_type.data = entry.meal_type
    edit_form.food_name.data = entry.food_name
    edit_form.location.data = entry.location or ''
    edit_form.member_ids.data = [entry.member_id]
    return render_template('meals/edit_entry.html', group=group, entry=entry, edit_form=edit_form, active_tab='history')

@meals_bp.route('/groups/<int:group_id>/entries/<int:entry_id>/edit', methods=['POST'])
@login_required
def edit_entry(group_id, entry_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
    group = MealsFamilyGroup.query.get_or_404(group_id)
    entry = MealsEntry.query.get_or_404(entry_id)
    if entry.family_group_id != group_id:
        abort(404)
    form = EditEntryForm()
    form.member_ids.choices = [(m.id, m.name) for m in group.members]
    if form.validate_on_submit():
        # Delete original and create new entries for each selected member (like log)
        db.session.delete(entry)
        for member_id in form.member_ids.data:
            new_entry = MealsEntry(
                family_group_id=group_id,
                member_id=member_id,
                food_name=form.food_name.data,
                location=form.location.data,
                meal_type=form.meal_type.data,
                date=form.date.data,
                created_by_id=current_user.id
            )
            db.session.add(new_entry)
        db.session.commit()
        flash('Entry updated.', 'success')
        return redirect(url_for('meals.history_view', group_id=group_id))
    for field, errors in form.errors.items():
        for error in errors:
            flash(f'Error in {field}: {error}', 'danger')
    return render_template('meals/edit_entry.html', group=group, entry=entry, edit_form=form, active_tab='history')

@meals_bp.route('/groups/<int:group_id>/entries/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_entry(group_id, entry_id):
    if not is_user_in_group(current_user, group_id):
        return {"error": "Unauthorized"}, 403
    entry = MealsEntry.query.get_or_404(entry_id)
    if entry.family_group_id != group_id:
        return {"error": "Invalid entry"}, 400
    db.session.delete(entry)
    db.session.commit()
    return {"success": True}

@meals_bp.route('/groups/<int:group_id>/api/suggestions/food')
@login_required
def suggest_food(group_id):
    if not is_user_in_group(current_user, group_id):
        return {"error": "Unauthorized"}, 403
    query = request.args.get('q', '').lower()
    suggestions = db.session.query(MealsEntry.food_name).filter(
        MealsEntry.family_group_id == group_id,
        MealsEntry.food_name.ilike(f'%{query}%')
    ).distinct().limit(10).all()
    return [s[0] for s in suggestions]

@meals_bp.route('/groups/<int:group_id>/api/suggestions/location')
@login_required
def suggest_location(group_id):
    if not is_user_in_group(current_user, group_id):
        return {"error": "Unauthorized"}, 403
    query = request.args.get('q', '').lower()
    suggestions = db.session.query(MealsEntry.location).filter(
        MealsEntry.family_group_id == group_id,
        MealsEntry.location.ilike(f'%{query}%'),
        MealsEntry.location.isnot(None)
    ).distinct().limit(10).all()
    return [s[0] for s in suggestions]
