from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from sqlalchemy import func
from flask_login import login_required, current_user
import calendar
from datetime import date, timedelta, datetime
from app import db
from app.models import User
from app.projects.meals.models import MealsFamilyGroup, MealsFamilyMember, MealsEntry
from app.projects.meals.forms import CreateFamilyGroupForm, InviteMemberForm, AddGuestMemberForm, LogMealForm
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
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error in {field}: {error}', 'danger')
                
    return redirect(url_for('meals.group_detail', group_id=group_id))

@meals_bp.route('/groups/<int:group_id>')
@login_required
def group_detail(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
        
    group = MealsFamilyGroup.query.get_or_404(group_id)
    invite_form = InviteMemberForm()
    guest_form = AddGuestMemberForm()
    
    log_form = LogMealForm()
    log_form.member_ids.choices = [(m.id, m.name) for m in group.members]
    
    recent_entries = MealsEntry.query.filter_by(family_group_id=group_id).order_by(MealsEntry.date.desc(), MealsEntry.created_at.desc()).limit(20).all()
    
    # Common Meals Stats
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
    ).order_by(func.count(MealsEntry.id).desc()).limit(10).all()
    
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
    
    return render_template('meals/group_detail.html', 
                           group=group, 
                           invite_form=invite_form, 
                           guest_form=guest_form,
                           log_form=log_form,
                           recent_entries=recent_entries,
                           common_meals=common_meals,
                           home_count=home_count,
                           out_count=out_count,
                           member_filter=member_filter)

@meals_bp.route('/groups/<int:group_id>/calendar')
@login_required
def calendar_view(group_id):
    if not is_user_in_group(current_user, group_id):
        abort(404)
        
    group = MealsFamilyGroup.query.get_or_404(group_id)
    view_type = request.args.get('view', 'monthly') # 'monthly' or 'weekly'
    
    # Get current date or date from params
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', date.today().month, type=int)
    day = request.args.get('day', date.today().day, type=int)
    member_filter = request.args.get('member_id', type=int)
    
    current_focus = date(year, month, day)
    
    if view_type == 'monthly':
        # ... existing logic ...
        start_date = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        end_date = date(year, month, last_day)
        
        # Adjust start_date to the beginning of the week (Sunday)
        start_date = start_date - timedelta(days=(start_date.weekday() + 1) % 7)
        # Adjust end_date to the end of the week (Saturday)
        end_date = end_date + timedelta(days=(5 - end_date.weekday() + 1) % 7)
        
        prev_date = (date(year, month, 1) - timedelta(days=1))
        next_date = (date(year, month, 1) + timedelta(days=32)).replace(day=1)
    else: # weekly
        # Adjust start_date to the beginning of the current week (Sunday)
        start_date = current_focus - timedelta(days=(current_focus.weekday() + 1) % 7)
        end_date = start_date + timedelta(days=6)
        
        prev_date = start_date - timedelta(days=7)
        next_date = start_date + timedelta(days=7)

    # Fetch entries
    query = MealsEntry.query.filter(
        MealsEntry.family_group_id == group_id,
        MealsEntry.date >= start_date,
        MealsEntry.date <= end_date
    )
    
    if member_filter:
        query = query.filter(MealsEntry.member_id == member_filter)
        
    entries = query.order_by(MealsEntry.date, MealsEntry.meal_type).all()
    
    # Group entries by date and meal type, then by food+location for "Family Overlay"
    calendar_data = {}
    curr = start_date
    while curr <= end_date:
        calendar_data[curr] = {
            'Breakfast': {}, # { 'food+loc': [entries] }
            'Lunch': {},
            'Dinner': {}
        }
        curr += timedelta(days=1)
        
    for entry in entries:
        if entry.date in calendar_data:
            meal_key = f"{entry.food_name}|{entry.location or ''}"
            if meal_key not in calendar_data[entry.date][entry.meal_type]:
                calendar_data[entry.date][entry.meal_type][meal_key] = []
            calendar_data[entry.date][entry.meal_type][meal_key].append(entry)

    return render_template('meals/calendar.html',
                           group=group,
                           view_type=view_type,
                           calendar_data=calendar_data,
                           start_date=start_date,
                           end_date=end_date,
                           current_focus=current_focus,
                           prev_date=prev_date,
                           next_date=next_date,
                           month_name=calendar.month_name[month],
                           year=year,
                           date=date,
                           member_filter=member_filter)

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
