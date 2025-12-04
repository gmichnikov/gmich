from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

spanish_vocab_invaders_bp = Blueprint('spanish_vocab_invaders', __name__, 
                                      template_folder='templates')

@spanish_vocab_invaders_bp.route('/')
def index():
    """Display the Spanish Vocab Invaders game - self-contained HTML with inline CSS/JS"""
    log_project_visit('spanish_vocab_invaders', 'Spanish Vocab Invaders')
    return render_template('spanish_vocab_invaders.html')


