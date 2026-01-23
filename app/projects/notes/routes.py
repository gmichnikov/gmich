from flask import Blueprint, render_template
from flask_login import login_required
from app.utils.logging import log_project_visit

notes_bp = Blueprint('notes', __name__,
                     url_prefix='/notes',
                     template_folder='templates')


@notes_bp.route('/')
@login_required
def index():
    log_project_visit('notes', 'Notes')
    return render_template('notes/index.html')
