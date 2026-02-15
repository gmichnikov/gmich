from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import current_user, login_required
from app.projects.registry import get_homepage_items, get_children_of_category, get_project_by_id
from app.forms import FeedbackForm
from app.utils.email_service import send_email
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Get homepage items (projects and categories, excluding child projects)
    is_authenticated = current_user.is_authenticated
    is_admin = getattr(current_user, 'is_admin', False) if is_authenticated else False
    projects = get_homepage_items(is_authenticated, is_admin)
    
    return render_template('index.html', projects=projects)

@main_bp.route('/games')
def games():
    # Get the Simple Games category info
    category = get_project_by_id('simple_games')
    
    # Get all child projects
    is_authenticated = current_user.is_authenticated
    is_admin = getattr(current_user, 'is_admin', False) if is_authenticated else False
    items = get_children_of_category('simple_games', is_authenticated, is_admin)
    
    return render_template('category.html', category=category, items=items)

@main_bp.route('/game-night-tools')
def game_night_tools():
    # Get the Game Night Tools category info
    category = get_project_by_id('game_night_tools')
    
    # Get all child projects
    is_authenticated = current_user.is_authenticated
    is_admin = getattr(current_user, 'is_admin', False) if is_authenticated else False
    items = get_children_of_category('game_night_tools', is_authenticated, is_admin)
    
    return render_template('category.html', category=category, items=items)

@main_bp.route('/coding-bootcamp')
def coding_bootcamp():
    # Get the Coding Bootcamp category info
    category = get_project_by_id('coding_bootcamp')
    
    # Get all child projects
    is_authenticated = current_user.is_authenticated
    is_admin = getattr(current_user, 'is_admin', False) if is_authenticated else False
    items = get_children_of_category('coding_bootcamp', is_authenticated, is_admin)
    
    return render_template('category.html', category=category, items=items)

@main_bp.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():
    """Feedback page for authenticated users"""
    form = FeedbackForm()
    if form.validate_on_submit():
        try:
            admin_email = os.getenv('ADMIN_EMAIL')
            if not admin_email:
                flash('Feedback service is currently unavailable. Please try again later.', 'error')
                return redirect(url_for('main.feedback'))
            
            # Prepare email content
            user_email = current_user.email
            subject = f"Feedback from {user_email}: {form.subject.data}"
            text_content = f"""Feedback from {user_email}:

Subject: {form.subject.data}

Message:
{form.message.data}

---
This feedback was submitted from gregmichnikov.com
"""
            
            # Send email to admin
            send_email(admin_email, subject, text_content)
            
            flash('Thank you for your feedback! We\'ll get back to you soon.', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            flash('There was an error sending your feedback. Please try again later.', 'error')
    
    return render_template('feedback.html', form=form)

@main_bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404