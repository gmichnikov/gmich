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
    from datetime import date
    user_teams = BasketballTeam.query.filter_by(user_id=current_user.id).order_by(BasketballTeam.name).all()
    user_games = BasketballGame.query.filter_by(user_id=current_user.id).order_by(BasketballGame.game_date.desc(), BasketballGame.created_at.desc()).all()
    return render_template('basketball_tracker/index.html', 
                           teams=user_teams, 
                           games=user_games,
                           today_date=date.today().isoformat())


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


def calculate_game_stats(game):
    """Helper to calculate stats for both teams in a game"""
    stats = {
        'team1': {'id': game.team1_id, 'name': game.team1.name, 'points': 0, 'fgm': 0, 'fga': 0, 'tp_m': 0, 'tp_a': 0, 'ftm': 0, 'fta': 0, 'to': 0, 'reb': 0, 'to_travel': 0, 'to_steal': 0, 'to_other': 0, 'shot_layup_m': 0, 'shot_layup_a': 0, 'shot_close2_m': 0, 'shot_close2_a': 0, 'shot_far2_m': 0, 'shot_far2_a': 0},
        'team2': {'id': game.team2_id, 'name': game.team2.name, 'points': 0, 'fgm': 0, 'fga': 0, 'tp_m': 0, 'tp_a': 0, 'ftm': 0, 'fta': 0, 'to': 0, 'reb': 0, 'to_travel': 0, 'to_steal': 0, 'to_other': 0, 'shot_layup_m': 0, 'shot_layup_a': 0, 'shot_close2_m': 0, 'shot_close2_a': 0, 'shot_far2_m': 0, 'shot_far2_a': 0}
    }
    
    events = BasketballEvent.query.filter_by(game_id=game.id).all()
    
    for e in events:
        team_key = 'team1' if e.team_id == game.team1_id else 'team2'
        t = stats[team_key]
        
        if e.event_category == 'make':
            if e.event_subcategory == 'Free Throw':
                t['points'] += 1
                t['ftm'] += 1
                t['fta'] += 1
            elif e.event_subcategory == '3-Pointer':
                t['points'] += 3
                t['tp_m'] += 1
                t['tp_a'] += 1
            else:
                # 2-pointers
                t['points'] += 2
                t['fgm'] += 1
                t['fga'] += 1
                if e.event_subcategory == 'Layup': 
                    t['shot_layup_m'] += 1
                    t['shot_layup_a'] += 1
                elif e.event_subcategory == 'Close 2': 
                    t['shot_close2_m'] += 1
                    t['shot_close2_a'] += 1
                elif e.event_subcategory == 'Far 2': 
                    t['shot_far2_m'] += 1
                    t['shot_far2_a'] += 1
                
        elif e.event_category == 'miss':
            if e.event_subcategory == 'Free Throw':
                t['fta'] += 1
            elif e.event_subcategory == '3-Pointer':
                t['tp_a'] += 1
            else:
                t['fga'] += 1
                if e.event_subcategory == 'Layup': t['shot_layup_a'] += 1
                elif e.event_subcategory == 'Close 2': t['shot_close2_a'] += 1
                elif e.event_subcategory == 'Far 2': t['shot_far2_a'] += 1
                
        elif e.event_category == 'turnover':
            t['to'] += 1
            if e.event_subcategory == 'Traveling': t['to_travel'] += 1
            elif e.event_subcategory == 'Steal': t['to_steal'] += 1
            else: t['to_other'] += 1
            
        elif e.event_category == 'rebound':
            t['reb'] += 1

    # Calculate percentages with division-by-zero protection
    for key in ['team1', 'team2']:
        t = stats[key]
        t['fg_pct'] = (t['fgm'] / t['fga'] * 100) if t['fga'] > 0 else None
        t['tp_pct'] = (t['tp_m'] / t['tp_a'] * 100) if t['tp_a'] > 0 else None
        t['ft_pct'] = (t['ftm'] / t['fta'] * 100) if t['fta'] > 0 else None
        
    return stats


@basketball_tracker.route('/game/<int:game_id>/stats')
@login_required
def get_game_stats(game_id):
    """API endpoint for game statistics"""
    game_obj = BasketballGame.query.get_or_404(game_id)
    if game_obj.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    stats = calculate_game_stats(game_obj)
    return jsonify(stats)


@basketball_tracker.route('/game/<int:game_id>/delete', methods=['DELETE'])
@login_required
def delete_game(game_id):
    """Delete a game and all its events"""
    game_obj = BasketballGame.query.get_or_404(game_id)
    if game_obj.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(game_obj)
    db.session.commit()
    
    return jsonify({'success': True})

