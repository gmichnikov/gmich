"""
Basketball Tracker Routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from flask_login import login_required, current_user
from app import db
from app.projects.basketball_tracker.models import BasketballTeam, BasketballGame, BasketballEvent

basketball_tracker = Blueprint('basketball_tracker', __name__,
                               template_folder='templates',
                               static_folder='static',
                               static_url_path='/static')


@basketball_tracker.route('/')
@login_required
def index():
    """Home page showing games list and teams navigation"""
    user_teams = BasketballTeam.query.filter_by(user_id=current_user.id).order_by(BasketballTeam.name).all()
    user_games = BasketballGame.query.filter_by(user_id=current_user.id).order_by(BasketballGame.game_date.desc(), BasketballGame.created_at.desc()).all()
    return render_template('basketball_tracker/index.html', teams=user_teams, games=user_games)


@basketball_tracker.route('/games/create', methods=['POST'])
@login_required
def create_game():
    """Create a new game"""
    team1_id = request.form.get('team1_id', type=int)
    team2_id = request.form.get('team2_id', type=int)
    game_date_str = request.form.get('game_date')
    
    if not team1_id or not team2_id or not game_date_str:
        flash('All fields are required to create a game', 'error')
        return redirect(url_for('basketball_tracker.index'))
    
    if team1_id == team2_id:
        flash('A team cannot play against itself', 'error')
        return redirect(url_for('basketball_tracker.index'))
    
    try:
        from datetime import datetime
        game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format', 'error')
        return redirect(url_for('basketball_tracker.index'))
    
    # Verify teams belong to user
    team1 = BasketballTeam.query.get(team1_id)
    team2 = BasketballTeam.query.get(team2_id)
    
    if not team1 or team1.user_id != current_user.id or not team2 or team2.user_id != current_user.id:
        flash('Invalid teams selected', 'error')
        return redirect(url_for('basketball_tracker.index'))
    
    new_game = BasketballGame(
        user_id=current_user.id,
        team1_id=team1_id,
        team2_id=team2_id,
        game_date=game_date,
        current_period=1
    )
    db.session.add(new_game)
    db.session.commit()
    
    flash(f'Game between {team1.name} and {team2.name} created!', 'success')
    return redirect(url_for('basketball_tracker.game', game_id=new_game.id))


@basketball_tracker.route('/teams')
@login_required
def teams():
    """Teams management page"""
    user_teams = BasketballTeam.query.filter_by(user_id=current_user.id).order_by(BasketballTeam.name).all()
    return render_template('basketball_tracker/teams.html', teams=user_teams)


@basketball_tracker.route('/teams/create', methods=['POST'])
@login_required
def create_team():
    """Create a new team"""
    team_name = request.form.get('team_name', '').strip()
    
    if not team_name:
        flash('Team name is required', 'error')
        return redirect(url_for('basketball_tracker.teams'))
    
    team = BasketballTeam(
        user_id=current_user.id,
        name=team_name
    )
    db.session.add(team)
    db.session.commit()
    
    flash(f'Team "{team_name}" created successfully', 'success')
    return redirect(url_for('basketball_tracker.teams'))


@basketball_tracker.route('/teams/<int:team_id>/delete', methods=['POST'])
@login_required
def delete_team(team_id):
    """Delete a team"""
    team = BasketballTeam.query.get_or_404(team_id)
    
    # Verify team belongs to current user
    if team.user_id != current_user.id:
        flash('You do not have permission to delete this team', 'error')
        return redirect(url_for('basketball_tracker.teams'))
    
    # Check if team is used in any games
    games_with_team = BasketballGame.query.filter(
        (BasketballGame.team1_id == team_id) | (BasketballGame.team2_id == team_id)
    ).first()
    
    if games_with_team:
        flash(f'Cannot delete "{team.name}" - it is used in existing games', 'error')
        return redirect(url_for('basketball_tracker.teams'))
    
    # Safe to delete
    team_name = team.name
    db.session.delete(team)
    db.session.commit()
    
    flash(f'Team "{team_name}" deleted successfully', 'success')
    return redirect(url_for('basketball_tracker.teams'))


@basketball_tracker.route('/game/<int:game_id>')
@login_required
def game(game_id):
    """Game tracking/viewing page"""
    game_obj = BasketballGame.query.get_or_404(game_id)
    
    if game_obj.user_id != current_user.id:
        flash('You do not have permission to view this game', 'error')
        return redirect(url_for('basketball_tracker.index'))
    
    # Fetch initial events to pass to template
    initial_events = BasketballEvent.query.filter_by(game_id=game_id).order_by(BasketballEvent.created_at.desc()).all()
        
    return render_template('basketball_tracker/game.html', game=game_obj, initial_events=initial_events)


@basketball_tracker.route('/game/<int:game_id>/event', methods=['POST'])
@login_required
def add_event(game_id):
    """Add a new game event via AJAX"""
    game_obj = BasketballGame.query.get_or_404(game_id)
    if game_obj.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    team_id = data.get('team_id')
    period = data.get('period')
    category = data.get('event_category')
    subcategory = data.get('event_subcategory')
    
    if not all([team_id, period, category, subcategory]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Verify team belongs to game
    if team_id not in [game_obj.team1_id, game_obj.team2_id]:
        return jsonify({'error': 'Invalid team for this game'}), 400
    
    new_event = BasketballEvent(
        game_id=game_id,
        team_id=team_id,
        period=period,
        event_category=category,
        event_subcategory=subcategory
    )
    db.session.add(new_event)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'event': {
            'id': new_event.id,
            'team_id': new_event.team_id,
            'team_name': new_event.team.name,
            'period': new_event.period,
            'category': new_event.event_category,
            'subcategory': new_event.event_subcategory,
            'created_at': new_event.created_at.isoformat()
        }
    })


@basketball_tracker.route('/game/<int:game_id>/event/undo', methods=['DELETE'])
@login_required
def undo_event(game_id):
    """Undo the most recent event for a game"""
    game_obj = BasketballGame.query.get_or_404(game_id)
    if game_obj.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    last_event = BasketballEvent.query.filter_by(game_id=game_id).order_by(BasketballEvent.created_at.desc()).first()
    
    if not last_event:
        return jsonify({'error': 'No events to undo'}), 400
    
    deleted_id = last_event.id
    db.session.delete(last_event)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'deleted_event_id': deleted_id
    })


@basketball_tracker.route('/game/<int:game_id>/events', methods=['GET'])
@login_required
def get_events(game_id):
    """Fetch all events for a game"""
    game_obj = BasketballGame.query.get_or_404(game_id)
    if game_obj.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    events = BasketballEvent.query.filter_by(game_id=game_id).order_by(BasketballEvent.created_at.desc()).all()
    
    return jsonify({
        'events': [{
            'id': e.id,
            'team_id': e.team_id,
            'team_name': e.team.name,
            'period': e.period,
            'category': e.event_category,
            'subcategory': e.event_subcategory,
            'created_at': e.created_at.isoformat()
        } for e in events]
    })


@basketball_tracker.route('/game/<int:game_id>/period', methods=['POST'])
@login_required
def update_period(game_id):
    """Update current game period"""
    game_obj = BasketballGame.query.get_or_404(game_id)
    if game_obj.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    new_period = data.get('period')
    
    if new_period is None:
        return jsonify({'error': 'No period provided'}), 400
         
    game_obj.current_period = new_period
    db.session.commit()
    
    return jsonify({'success': True, 'period': game_obj.current_period})
