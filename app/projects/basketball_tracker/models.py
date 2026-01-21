"""
Basketball Tracker Models
"""
from app import db
from datetime import datetime


class BasketballTeam(db.Model):
    """Team model for basketball tracker"""
    __tablename__ = 'basketball_team'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='basketball_teams')
    home_games = db.relationship('BasketballGame', foreign_keys='BasketballGame.team1_id', backref='team1', lazy='dynamic')
    away_games = db.relationship('BasketballGame', foreign_keys='BasketballGame.team2_id', backref='team2', lazy='dynamic')


class BasketballGame(db.Model):
    """Game model for basketball tracker"""
    __tablename__ = 'basketball_game'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    team1_id = db.Column(db.Integer, db.ForeignKey('basketball_team.id'), nullable=False)
    team2_id = db.Column(db.Integer, db.ForeignKey('basketball_team.id'), nullable=False)
    game_date = db.Column(db.Date, nullable=False)
    current_period = db.Column(db.Integer, default=1)  # 1-4 for quarters, 5+ for OT
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='basketball_games')
    events = db.relationship('BasketballEvent', backref='game', lazy='dynamic', cascade='all, delete-orphan')


class BasketballEvent(db.Model):
    """Event model for tracking game actions"""
    __tablename__ = 'basketball_event'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('basketball_game.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('basketball_team.id'), nullable=False)
    period = db.Column(db.Integer, nullable=False)
    event_category = db.Column(db.String(50), nullable=False)  # 'make', 'miss', 'turnover', 'rebound'
    event_subcategory = db.Column(db.String(50), nullable=False)  # shot type, turnover type, or rebound type
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    team = db.relationship('BasketballTeam', backref='events')
