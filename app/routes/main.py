from flask import Blueprint, render_template
from flask_login import current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # Project data - will be expanded as new projects are added
    projects = [
        {
            'name': 'Todo App',
            'description': 'A simple and elegant todo list application to manage your tasks',
            'icon': '✓',
            'url': '/todo',
            'available': True
        },
        {
            'name': 'Calculator',
            'description': 'A powerful calculator with advanced mathematical functions',
            'icon': '🔢',
            'url': '/calculator',
            'available': False
        },
        {
            'name': 'Notes',
            'description': 'Take and organize notes with markdown support',
            'icon': '📝',
            'url': '/notes',
            'available': False
        },
        {
            'name': 'Weather App',
            'description': 'Check current weather and forecasts for any location',
            'icon': '🌤',
            'url': '/weather',
            'available': False
        }
    ]
    
    return render_template('index.html', projects=projects)

@main_bp.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404