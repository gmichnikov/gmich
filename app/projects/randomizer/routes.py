from flask import Blueprint, render_template, jsonify
from flask_login import current_user
from app import db
from app.models import LogEntry
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


@randomizer_bp.route('/api/log/randomize', methods=['POST'])
def log_randomize():
    """Called by the client when items are randomized."""
    db.session.add(LogEntry(
        actor_id=current_user.id if current_user.is_authenticated else None,
        project='randomizer',
        category='Randomize',
        description='Ran a randomization',
    ))
    db.session.commit()
    return jsonify({'ok': True})
