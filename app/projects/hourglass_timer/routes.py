from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

hourglass_timer_bp = Blueprint('hourglass_timer', __name__, 
                               template_folder='templates')

@hourglass_timer_bp.route('/')
def index():
    """Display the Hourglass Timer - self-contained HTML with inline CSS/JS"""
    log_project_visit('hourglass_timer', 'Hourglass Timer')
    return render_template('hourglass_timer.html')
