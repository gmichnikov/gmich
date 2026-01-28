"""
BetFake Routes
"""
from flask import Blueprint, render_template
from flask_login import login_required

betfake_bp = Blueprint('betfake', __name__,
                       template_folder='templates',
                       static_folder='static',
                       static_url_path='/static')

@betfake_bp.route('/')
@login_required
def index():
    """BetFake Home Page"""
    return render_template('betfake/index.html')
