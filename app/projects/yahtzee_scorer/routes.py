from flask import Blueprint, render_template, jsonify
from flask_login import current_user
from app import db
from app.models import LogEntry
from app.utils.logging import log_project_visit

yahtzee_scorer_bp = Blueprint('yahtzee_scorer', __name__, 
                             template_folder='templates')

@yahtzee_scorer_bp.route('/')
def index():
    """Display the Yahtzee Scorer"""
    log_project_visit('yahtzee_scorer', 'Yahtzee Scorer')
    return render_template('yahtzee_scorer.html')


@yahtzee_scorer_bp.route('/api/log/new-game', methods=['POST'])
def log_new_game():
    """Called by the client when a new game starts."""
    db.session.add(LogEntry(
        actor_id=current_user.id if current_user.is_authenticated else None,
        project='yahtzee_scorer',
        category='New Game',
        description='Started a new Yahtzee game',
    ))
    db.session.commit()
    return jsonify({'ok': True})
