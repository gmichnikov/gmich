from flask import Blueprint, render_template
from app.utils.logging import log_project_visit

randomizer_bp = Blueprint(
    'randomizer',
    __name__,
    template_folder='templates',
    static_folder='static',
    static_url_path='/randomizer/static',
)


@randomizer_bp.route('/')
def index():
    log_project_visit('randomizer', 'Randomizer')
    return render_template('randomizer/index.html')
