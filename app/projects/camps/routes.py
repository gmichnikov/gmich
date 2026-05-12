from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required
from app import db
from app.projects.camps.models import Camp, CampSession, CampTagCategory, CampTag
from app.projects.camps.forms import CampForm, CampSessionForm, CampTagCategoryForm, CampTagForm
from app.projects.camps.weeks import get_summer_2026_mondays
from app.projects.camps.filters import apply_filters
from app.core.admin import admin_required
from app.utils.logging import log_project_visit
from datetime import datetime, date, time

camps_bp = Blueprint(
    "camps",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/camps/static",
    url_prefix="/camps",
)

# --- Public Routes ---

@camps_bp.route("/")
def index():
    log_project_visit("camps", "Camps")
    
    # Get all camps for initial query
    query = Camp.query
    
    # Apply filters from query params
    query = apply_filters(query, request.args)
    
    # Default sort: A-Z by name
    camps = query.order_by(Camp.name).all()
    
    # Data for filter sidebar
    towns = db.session.query(Camp.city).distinct().order_by(Camp.city).all()
    towns = [t[0] for t in towns]
    
    summer_mondays = get_summer_2026_mondays()
    tag_categories = CampTagCategory.query.order_by(CampTagCategory.name).all()
    
    return render_template("camps/index.html", 
                           camps=camps, 
                           towns=towns, 
                           summer_mondays=summer_mondays,
                           tag_categories=tag_categories)

@camps_bp.route("/camp/<int:camp_id>")
def camp_detail(camp_id):
    camp = Camp.query.get_or_404(camp_id)
    # Order sessions by start_date, then name, then id
    sessions = sorted(camp.sessions, key=lambda s: (s.start_date, s.name or "", s.id))
    return render_template("camps/camp_detail.html", camp=camp, sessions=sessions)

@camps_bp.route("/session/<int:session_id>")
def session_detail(session_id):
    session = CampSession.query.get_or_404(session_id)
    return render_template("camps/session_detail.html", session=session)

# --- Admin Routes ---

@camps_bp.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    camps = Camp.query.order_by(Camp.name).all()
    tag_categories = CampTagCategory.query.order_by(CampTagCategory.name).all()
    return render_template("camps/admin/dashboard.html", camps=camps, tag_categories=tag_categories)

# Camp CRUD
@camps_bp.route("/admin/camp/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_camp():
    form = CampForm()
    # Populate tag choices grouped by category
    tags = CampTag.query.join(CampTagCategory).order_by(CampTagCategory.name, CampTag.name).all()
    form.tag_ids.choices = [(t.id, f"{t.category.name}: {t.name}") for t in tags]
    
    if form.validate_on_submit():
        # Check for potential duplicate (same name and city)
        existing = Camp.query.filter_by(name=form.name.data, city=form.city.data).first()
        if existing:
            flash(f"Warning: A camp named '{form.name.data}' already exists in {form.city.data}.", "warning")
            
        camp = Camp(
            name=form.name.data,
            website_url=form.website_url.data,
            email=form.email.data,
            phone=form.phone.data,
            address=form.address.data,
            city=form.city.data,
            state=form.state.data,
            zip=form.zip.data
        )
        if form.tag_ids.data:
            selected_tags = CampTag.query.filter(CampTag.id.in_(form.tag_ids.data)).all()
            camp.tags = selected_tags
            
        db.session.add(camp)
        db.session.commit()
        flash(f"Camp '{camp.name}' added successfully.")
        return redirect(url_for("camps.admin_dashboard"))
        
    return render_template("camps/admin/camp_form.html", form=form, title="Add Camp")

def parse_time_string(time_str):
    if not time_str:
        return None
    try:
        # Try common formats
        for fmt in ('%I:%M%p', '%I:%M %p', '%H:%M'):
            try:
                return datetime.strptime(time_str.strip().upper(), fmt).time()
            except ValueError:
                continue
    except Exception:
        pass
    return None

@camps_bp.route("/admin/camp/<int:camp_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_camp(camp_id):
    camp = Camp.query.get_or_404(camp_id)
    form = CampForm(obj=camp)
    tags = CampTag.query.join(CampTagCategory).order_by(CampTagCategory.name, CampTag.name).all()
    form.tag_ids.choices = [(t.id, f"{t.category.name}: {t.name}") for t in tags]
    
    if request.method == "GET":
        form.tag_ids.data = [t.id for t in camp.tags]
        
    if form.validate_on_submit():
        form.populate_obj(camp)
        if form.tag_ids.data:
            selected_tags = CampTag.query.filter(CampTag.id.in_(form.tag_ids.data)).all()
            camp.tags = selected_tags
        else:
            camp.tags = []
            
        db.session.commit()
        flash(f"Camp '{camp.name}' updated successfully.")
        return redirect(url_for("camps.admin_dashboard"))
    
    # Calculate common vs varying fields for sessions
    sessions = sorted(camp.sessions, key=lambda s: s.start_date)
    common_fields = {}
    varying_fields = set()
    
    if sessions:
        first = sessions[0]
        fields_to_check = ['name', 'formatted_start_time', 'formatted_end_time', 'age_min', 'age_max', 'grade_min', 'grade_max', 'price']
        
        # Initialize common fields with first session
        for field in fields_to_check:
            common_fields[field] = getattr(first, field)
            
        # Check for variations
        for s in sessions[1:]:
            for field in fields_to_check:
                if getattr(s, field) != common_fields[field]:
                    varying_fields.add(field)
        
        # Clean up common_fields: remove those that vary
        for field in list(common_fields.keys()):
            if field in varying_fields:
                del common_fields[field]
                
    return render_template("camps/admin/camp_form.html", 
                           form=form, 
                           title=f"Edit {camp.name}", 
                           camp=camp, 
                           common_fields=common_fields,
                           varying_fields=varying_fields)

@camps_bp.route("/admin/camp/<int:camp_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_camp(camp_id):
    camp = Camp.query.get_or_404(camp_id)
    name = camp.name
    db.session.delete(camp)
    db.session.commit()
    flash(f"Camp '{name}' deleted.")
    return redirect(url_for("camps.admin_dashboard"))

# Session CRUD
@camps_bp.route("/admin/camp/<int:camp_id>/session/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_session(camp_id):
    camp = Camp.query.get_or_404(camp_id)
    form = CampSessionForm()
    
    # Populate summer weeks
    summer_mondays = get_summer_2026_mondays()
    form.additional_weeks.choices = [(m.isoformat(), f"Week of {m.strftime('%b %-d')}") for m in summer_mondays]
    
    if form.validate_on_submit():
        if form.start_date.data > form.end_date.data:
            flash("Error: Start date must be before or on end date.", "error")
        else:
            # Format times for DB
            start_time_str = form.start_time.data.strftime('%-I:%M%p').lower() if form.start_time.data else None
            end_time_str = form.end_time.data.strftime('%-I:%M%p').lower() if form.end_time.data else None
            
            # Create primary session
            primary_session = CampSession(
                camp_id=camp.id,
                name=form.name.data,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                start_time=start_time_str,
                end_time=end_time_str,
                age_min=form.age_min.data,
                age_max=form.age_max.data,
                grade_min=form.grade_min.data,
                grade_max=form.grade_max.data,
                price=form.price.data
            )
            db.session.add(primary_session)
            
            # Create additional weeks if selected
            duration = form.end_date.data - form.start_date.data
            count = 1
            if form.additional_weeks.data:
                for monday_str in form.additional_weeks.data:
                    monday_date = date.fromisoformat(monday_str)
                    # Skip if it's the same as the primary start date
                    if monday_date == form.start_date.data:
                        continue
                        
                    extra_session = CampSession(
                        camp_id=camp.id,
                        name=form.name.data,
                        start_date=monday_date,
                        end_date=monday_date + duration,
                        start_time=start_time_str,
                        end_time=end_time_str,
                        age_min=form.age_min.data,
                        age_max=form.age_max.data,
                        grade_min=form.grade_min.data,
                        grade_max=form.grade_max.data,
                        price=form.price.data
                    )
                    db.session.add(extra_session)
                    count += 1
            
            db.session.commit()
            flash(f"Added {count} session(s) to '{camp.name}'.")
            return redirect(url_for("camps.edit_camp", camp_id=camp.id))
            
    return render_template("camps/admin/session_form.html", form=form, camp=camp, title="Add Session")

@camps_bp.route("/admin/session/<int:session_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit_session(session_id):
    session = CampSession.query.get_or_404(session_id)
    form = CampSessionForm(obj=session)
    # Hide additional weeks on edit
    del form.additional_weeks
    
    if request.method == "GET":
        form.start_time.data = parse_time_string(session.start_time)
        form.end_time.data = parse_time_string(session.end_time)
    
    if form.validate_on_submit():
        if form.start_date.data > form.end_date.data:
            flash("Error: Start date must be before or on end date.", "error")
        else:
            form.populate_obj(session)
            # Re-format times for DB
            session.start_time = form.start_time.data.strftime('%-I:%M%p').lower() if form.start_time.data else None
            session.end_time = form.end_time.data.strftime('%-I:%M%p').lower() if form.end_time.data else None
            db.session.commit()
            flash("Session updated.")
            return redirect(url_for("camps.edit_camp", camp_id=session.camp_id))
            
    return render_template("camps/admin/session_form.html", form=form, camp=session.camp, title="Edit Session", session=session)

@camps_bp.route("/admin/session/<int:session_id>/duplicate")
@login_required
@admin_required
def duplicate_session(session_id):
    original = CampSession.query.get_or_404(session_id)
    new_session = CampSession(
        camp_id=original.camp_id,
        name=original.name,
        start_date=original.start_date,
        end_date=original.end_date,
        start_time=original.start_time,
        end_time=original.end_time,
        age_min=original.age_min,
        age_max=original.age_max,
        grade_min=original.grade_min,
        grade_max=original.grade_max,
        price=original.price
    )
    db.session.add(new_session)
    db.session.commit()
    flash("Session duplicated. You can now edit the dates.")
    return redirect(url_for("camps.edit_camp", camp_id=original.camp_id))

@camps_bp.route("/admin/session/<int:session_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_session(session_id):
    session = CampSession.query.get_or_404(session_id)
    camp_id = session.camp_id
    db.session.delete(session)
    db.session.commit()
    flash("Session deleted.")
    return redirect(url_for("camps.edit_camp", camp_id=camp_id))

# Tag Category CRUD
@camps_bp.route("/admin/category/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_category():
    form = CampTagCategoryForm()
    if form.validate_on_submit():
        category = CampTagCategory(name=form.name.data)
        db.session.add(category)
        db.session.commit()
        flash(f"Category '{category.name}' added.")
        return redirect(url_for("camps.admin_dashboard"))
    return render_template("camps/admin/category_form.html", form=form, title="Add Category")

# Tag CRUD
@camps_bp.route("/admin/tag/add", methods=["GET", "POST"])
@login_required
@admin_required
def add_tag():
    form = CampTagForm()
    categories = CampTagCategory.query.order_by(CampTagCategory.name).all()
    form.category_id.choices = [(c.id, c.name) for c in categories]
    
    if form.validate_on_submit():
        tag = CampTag(category_id=form.category_id.data, name=form.name.data)
        db.session.add(tag)
        db.session.commit()
        flash(f"Tag '{tag.name}' added.")
        return redirect(url_for("camps.admin_dashboard"))
    return render_template("camps/admin/tag_form.html", form=form, title="Add Tag")
