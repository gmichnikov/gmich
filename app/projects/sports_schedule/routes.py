from flask import Blueprint, render_template
from flask_login import login_required

from app.utils.logging import log_project_visit

sports_schedule_bp = Blueprint('sports_schedule', __name__,
                               url_prefix='/sports-schedule',
                               template_folder='templates',
                               static_folder='static',
                               static_url_path='/sports-schedule/static')


@sports_schedule_bp.route('/')
@login_required
def index():
    """Main page."""
    log_project_visit('sports_schedule', 'Sports Schedule')
    return render_template('sports_schedule/index.html')
