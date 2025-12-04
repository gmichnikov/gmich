from flask import Blueprint, render_template

connect4_bp = Blueprint('connect4', __name__, 
                        template_folder='templates')

@connect4_bp.route('/')
def index():
    """Display the Connect 4 game - self-contained HTML with inline CSS/JS"""
    return render_template('connect4.html')


