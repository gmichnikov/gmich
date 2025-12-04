from flask import Blueprint, render_template
from flask_login import current_user
from app.projects.registry import get_homepage_items, get_children_of_category, get_project_by_id

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Get homepage items (projects and categories, excluding child projects)
    projects = get_homepage_items(current_user.is_authenticated)
    
    return render_template('index.html', projects=projects)

@main_bp.route('/games')
def games():
    # Get the Simple Games category info
    category = get_project_by_id('simple_games')
    
    # Get all child projects
    items = get_children_of_category('simple_games', current_user.is_authenticated)
    
    return render_template('category.html', category=category, items=items)

@main_bp.route('/game-night-tools')
def game_night_tools():
    # Get the Game Night Tools category info
    category = get_project_by_id('game_night_tools')
    
    # Get all child projects
    items = get_children_of_category('game_night_tools', current_user.is_authenticated)
    
    return render_template('category.html', category=category, items=items)

@main_bp.route('/coding-bootcamp')
def coding_bootcamp():
    # Get the Coding Bootcamp category info
    category = get_project_by_id('coding_bootcamp')
    
    # Get all child projects
    items = get_children_of_category('coding_bootcamp', current_user.is_authenticated)
    
    return render_template('category.html', category=category, items=items)

@main_bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404