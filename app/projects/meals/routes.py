from flask import Blueprint, render_template
from flask_login import login_required

meals_bp = Blueprint('meals', __name__, 
                    url_prefix='/meals',
                    template_folder='templates',
                    static_folder='static')

@meals_bp.route('/')
@login_required
def index():
    return render_template('meals/index.html')
