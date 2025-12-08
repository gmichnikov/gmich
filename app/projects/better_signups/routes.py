"""
Better Signups - Routes
Handles signup list creation, management, and signups
"""
from flask import Blueprint, render_template

bp = Blueprint('better_signups', __name__,
               url_prefix='/better-signups',
               template_folder='templates',
               static_folder='static')


@bp.route('/')
def index():
    """Main Better Signups page"""
    return render_template('better_signups/index.html')

