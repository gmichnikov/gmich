from flask import Blueprint, render_template, jsonify
from flask_login import current_user
from app import db
from app.models import LogEntry
from app.utils.logging import log_project_visit

go_long_bp = Blueprint('go_long', __name__, 
                        template_folder='templates',
                        static_folder='static',
                        static_url_path='/projects/go_long/static')

@go_long_bp.route('/')
def index():
    log_project_visit('go_long', 'Go Long')
    return render_template('go_long.html')


@go_long_bp.route('/api/log/new-game', methods=['POST'])
def log_new_game():
    """Called by the client when a new game starts."""
    db.session.add(LogEntry(
        actor_id=current_user.id if current_user.is_authenticated else None,
        project='go_long',
        category='New Game',
        description='Started a new Go Long game',
    ))
    db.session.commit()
    return jsonify({'ok': True})
