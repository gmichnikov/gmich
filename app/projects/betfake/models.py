from datetime import datetime
from app import db

class BetfakeAccount(db.Model):
    __tablename__ = 'betfake_account'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, nullable=False, default=100.0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('betfake_accounts', lazy=True))

    def __repr__(self):
        return f'<BetfakeAccount {self.name} - ${self.balance}>'

class BetfakeGame(db.Model):
    __tablename__ = 'betfake_game'
    
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(100), unique=True, nullable=False)
    sport_key = db.Column(db.String(50), nullable=False)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    commence_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Scheduled') # Scheduled, Live, Completed
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    last_update = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f'<BetfakeGame {self.away_team} @ {self.home_team}>'

class BetfakeMarket(db.Model):
    __tablename__ = 'betfake_market'
    
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('betfake_game.id'), nullable=True) # Nullable for futures
    type = db.Column(db.String(20), nullable=False) # h2h (ML), spreads, totals, future
    label = db.Column(db.String(255), nullable=True) # e.g., "NBA Championship Winner 2026"
    outcome_name = db.Column(db.String(100), nullable=False) # e.g., "Lakers", "Over"
    odds = db.Column(db.Integer, nullable=False) # American odds (e.g., -110, 150)
    point_value = db.Column(db.Float, nullable=True) # For spreads and totals
    external_market_id = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    game = db.relationship('BetfakeGame', backref=db.backref('markets', lazy=True))

    def __repr__(self):
        return f'<BetfakeMarket {self.type} - {self.outcome_name} ({self.odds})>'

class BetfakeBet(db.Model):
    __tablename__ = 'betfake_bet'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('betfake_account.id'), nullable=False)
    market_id = db.Column(db.Integer, db.ForeignKey('betfake_market.id'), nullable=False)
    wager_amount = db.Column(db.Float, nullable=False)
    odds_at_time = db.Column(db.Integer, nullable=False)
    line_at_time = db.Column(db.Float, nullable=True)
    outcome_name_at_time = db.Column(db.String(100), nullable=False)
    potential_payout = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pending') # Pending, Won, Lost, Push
    placed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    settled_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('betfake_bets', lazy=True))
    account = db.relationship('BetfakeAccount', backref=db.backref('bets', lazy=True))
    market = db.relationship('BetfakeMarket', backref=db.backref('bets', lazy=True))

    def __repr__(self):
        return f'<BetfakeBet {self.wager_amount} on {self.outcome_name_at_time}>'

class BetfakeTransaction(db.Model):
    __tablename__ = 'betfake_transaction'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('betfake_account.id'), nullable=False)
    bet_id = db.Column(db.Integer, db.ForeignKey('betfake_bet.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False) # Can be positive (payout/bonus) or negative (wager)
    type = db.Column(db.String(50), nullable=False) # Wager, Payout, Account Creation
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('betfake_transactions', lazy=True))
    account = db.relationship('BetfakeAccount', backref=db.backref('transactions', lazy=True))
    bet = db.relationship('BetfakeBet', backref=db.backref('transactions', lazy=True))

    def __repr__(self):
        return f'<BetfakeTransaction {self.type}: {self.amount}>'
