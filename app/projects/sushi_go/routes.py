from flask import Blueprint, render_template, jsonify
from flask_login import current_user
from app import db
from app.models import LogEntry
from app.utils.logging import log_project_visit

sushi_go_bp = Blueprint('sushi_go', __name__, 
                        template_folder='templates')

@sushi_go_bp.route('/')
def index():
    """Display the Sushi Go Scorer - self-contained HTML with inline CSS/JS"""
    log_project_visit('sushi_go', 'Sushi Go Scorer')
    return render_template('sushi_go.html')


@sushi_go_bp.route('/api/log/new-game', methods=['POST'])
def log_new_game():
    """Called by the client when a new game starts."""
    db.session.add(LogEntry(
        actor_id=current_user.id if current_user.is_authenticated else None,
        project='sushi_go',
        category='New Game',
        description='Started a new Sushi Go game',
    ))
    db.session.commit()
    return jsonify({'ok': True})

