from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

sorry_cards_bp = Blueprint('sorry_cards', __name__, 
                           template_folder='templates')

@sorry_cards_bp.route('/')
def index():
    """Display the Sorry Cards Deck Simulator - self-contained HTML with inline CSS/JS"""
    log_project_visit('sorry_cards', 'Sorry Cards')
    return render_template('sorry_cards.html')


