"""
Basketball Tracker Routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from app import db
from app.projects.basketball_tracker.models import BasketballTeam, BasketballGame, BasketballEvent

basketball_tracker = Blueprint('basketball_tracker', __name__)


@basketball_tracker.route('/')
@login_required
def index():
    """Home page showing games list and teams navigation"""
    return render_template('basketball_tracker/index.html')


@basketball_tracker.route('/teams')
@login_required
def teams():
    """Teams management page"""
    return render_template('basketball_tracker/teams.html')


@basketball_tracker.route('/game/<int:game_id>')
@login_required
def game(game_id):
    """Game tracking/viewing page"""
    return render_template('basketball_tracker/game.html', game_id=game_id)
