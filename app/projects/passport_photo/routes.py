from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

passport_photo_bp = Blueprint('passport_photo', __name__, 
                             template_folder='templates')

@passport_photo_bp.route('/')
def index():
    """Display the Passport Photo tool"""
    log_project_visit('passport_photo', 'Passport Photo')
    return render_template('passport_photo/index.html')
