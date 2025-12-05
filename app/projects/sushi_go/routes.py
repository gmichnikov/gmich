from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

sushi_go_bp = Blueprint('sushi_go', __name__, 
                        template_folder='templates')

@sushi_go_bp.route('/')
def index():
    """Display the Sushi Go Scorer - self-contained HTML with inline CSS/JS"""
    log_project_visit('sushi_go', 'Sushi Go Scorer')
    return render_template('sushi_go.html')

