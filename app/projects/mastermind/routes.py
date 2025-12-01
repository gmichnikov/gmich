from flask import Blueprint, render_template

mastermind_bp = Blueprint('mastermind', __name__, 
                         template_folder='templates')

@mastermind_bp.route('/')
def index():
    """Display the Mastermind game - self-contained HTML with inline CSS/JS"""
    return render_template('mastermind.html')

