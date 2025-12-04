from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

mastermind_bp = Blueprint('mastermind', __name__, 
                         template_folder='templates')

@mastermind_bp.route('/')
def index():
    """Display the Mastermind game - self-contained HTML with inline CSS/JS"""
    log_project_visit('mastermind', 'Mastermind')
    return render_template('mastermind.html')

