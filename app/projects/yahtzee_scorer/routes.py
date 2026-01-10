from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

yahtzee_scorer_bp = Blueprint('yahtzee_scorer', __name__, 
                             template_folder='templates')

@yahtzee_scorer_bp.route('/')
def index():
    """Display the Yahtzee Scorer"""
    log_project_visit('yahtzee_scorer', 'Yahtzee Scorer')
    return render_template('yahtzee_scorer.html')
