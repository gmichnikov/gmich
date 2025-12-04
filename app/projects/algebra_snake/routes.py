from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

algebra_snake_bp = Blueprint('algebra_snake', __name__, 
                             template_folder='templates')

@algebra_snake_bp.route('/')
def index():
    """Display the Algebra Snake game - self-contained HTML with inline CSS/JS"""
    log_project_visit('algebra_snake', 'Algebra Snake')
    return render_template('algebra_snake.html')


