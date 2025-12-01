from flask import Blueprint, render_template
from flask_login import current_user
from app.projects.registry import get_projects_for_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Get projects from registry with availability based on user's auth status
    projects = get_projects_for_user(current_user.is_authenticated)
    
    return render_template('index.html', projects=projects)

@main_bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404