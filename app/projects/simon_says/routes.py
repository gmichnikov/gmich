from flask import Blueprint, render_template

simon_says_bp = Blueprint('simon_says', __name__, 
                         template_folder='templates')

@simon_says_bp.route('/')
def index():
    """Display the Simon Says game - self-contained HTML with inline CSS/JS"""
    return render_template('simon_says.html')


