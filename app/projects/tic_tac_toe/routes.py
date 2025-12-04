from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

tic_tac_toe_bp = Blueprint('tic_tac_toe', __name__, 
                          template_folder='templates')

@tic_tac_toe_bp.route('/')
def index():
    """Display the Tic-Tac-Toe game - self-contained HTML with inline CSS/JS"""
    log_project_visit('tic_tac_toe', 'Tic-Tac-Toe')
    return render_template('tic_tac_toe.html')

