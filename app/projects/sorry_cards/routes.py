from flask import Blueprint, render_template, jsonify
from flask_login import current_user
from app import db
from app.models import LogEntry
from app.utils.logging import log_project_visit

sorry_cards_bp = Blueprint('sorry_cards', __name__, 
                           template_folder='templates')

@sorry_cards_bp.route('/')
def index():
    """Display the Sorry Cards Deck Simulator - self-contained HTML with inline CSS/JS"""
    log_project_visit('sorry_cards', 'Sorry Cards')
    return render_template('sorry_cards.html')


@sorry_cards_bp.route('/api/log/new-game', methods=['POST'])
def log_new_game():
    """Called by the client when the deck is reshuffled (new game)."""
    db.session.add(LogEntry(
        actor_id=current_user.id if current_user.is_authenticated else None,
        project='sorry_cards',
        category='New Game',
        description='Started a new Sorry Cards game (reshuffled deck)',
    ))
    db.session.commit()
    return jsonify({'ok': True})


