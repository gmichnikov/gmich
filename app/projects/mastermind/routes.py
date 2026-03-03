from flask import Blueprint, render_template, jsonify
from flask_login import current_user
from app import db
from app.models import LogEntry
from app.utils.logging import log_project_visit

mastermind_bp = Blueprint('mastermind', __name__, 
                         template_folder='templates')

@mastermind_bp.route('/')
def index():
    """Display the Mastermind game - self-contained HTML with inline CSS/JS"""
    log_project_visit('mastermind', 'Mastermind')
    return render_template('mastermind.html')


@mastermind_bp.route('/api/log/new-game', methods=['POST'])
def log_new_game():
    """Called by the client when a new game starts."""
    db.session.add(LogEntry(
        actor_id=current_user.id if current_user.is_authenticated else None,
        project='mastermind',
        category='New Game',
        description='Started a new Mastermind game',
    ))
    db.session.commit()
    return jsonify({'ok': True})

