from app import db
from datetime import datetime
import enum

class GameStatus(enum.Enum):
    Scheduled = "Scheduled"
    Live = "Live"
    Completed = "Completed"

class MarketType(enum.Enum):
    h2h = "h2h"
    spreads = "spreads"
    totals = "totals"
    outrights = "outrights"

class BetStatus(enum.Enum):
    Pending = "Pending"
    Won = "Won"
    Lost = "Lost"
    Push = "Push"

class TransactionType(enum.Enum):
    Wager = "Wager"
    Payout = "Payout"
    Account_Creation = "Account_Creation"

class BetfakeSport(db.Model):
    __tablename__ = 'betfake_sports'
    id = db.Column(db.Integer, primary_key=True)
    sport_key = db.Column(db.String(100), unique=True, nullable=False)
    sport_title = db.Column(db.String(100), nullable=False)
    sport_group = db.Column(db.String(100), nullable=True)
    has_spreads = db.Column(db.Boolean, default=True)
    sync_scores = db.Column(db.Boolean, default=False)
    sync_odds = db.Column(db.Boolean, default=False)
    show_in_nav = db.Column(db.Boolean, default=False)
    is_outright = db.Column(db.Boolean, default=False)
    preferred_label = db.Column(db.String(100), nullable=True)

    @property
    def display_title(self):
        return self.preferred_label if self.preferred_label else self.sport_title

    def __repr__(self):
        return f'<BetfakeSport {self.sport_title} ({self.sport_key})>'

class BetfakeAccount(db.Model):
    __tablename__ = 'betfake_accounts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, nullable=False, default=100.0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('betfake_accounts', lazy=True))

    def __repr__(self):
        return f'<BetfakeAccount {self.name} - ${self.balance}>'

class BetfakeGame(db.Model):
    __tablename__ = 'betfake_games'
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(100), unique=True, nullable=False)
    sport_key = db.Column(db.String(100), nullable=False)
    sport_title = db.Column(db.String(100), nullable=False)
    home_team = db.Column(db.String(100), nullable=True) # Nullable for futures
    away_team = db.Column(db.String(100), nullable=True) # Nullable for futures
    commence_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum(GameStatus), nullable=False, default=GameStatus.Scheduled)
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    last_update = db.Column(db.DateTime, nullable=True)

    @property
    def display_sport_title(self):
        """Returns the preferred label of the sport if available, otherwise the API title."""
        # Using a direct query here. In a high-traffic app this might be better handled 
        # with a relationship or pre-fetching, but for this app it's fine.
        from app.projects.betfake.models import BetfakeSport
        sport = BetfakeSport.query.filter_by(sport_key=self.sport_key).first()
        if sport:
            return sport.display_title
        return self.sport_title

    def __repr__(self):
        if self.home_team and self.away_team:
            return f'<BetfakeGame {self.home_team} vs {self.away_team} @ {self.commence_time}>'
        return f'<BetfakeGame {self.sport_title} @ {self.commence_time}>'

class BetfakeMarket(db.Model):
    __tablename__ = 'betfake_markets'
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('betfake_games.id'), nullable=True) # Nullable for outrights
    type = db.Column(db.Enum(MarketType), nullable=False)
    label = db.Column(db.String(255), nullable=True)
    bookmaker_key = db.Column(db.String(100), nullable=False)
    external_market_id = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    marked_inactive_at = db.Column(db.DateTime, nullable=True)
    last_update = db.Column(db.DateTime, nullable=True) # Timestamp from API

    game = db.relationship('BetfakeGame', backref=db.backref('markets', lazy=True))

    def __repr__(self):
        return f'<BetfakeMarket {self.type.value} - {self.bookmaker_key}>'

class BetfakeOutcome(db.Model):
    __tablename__ = 'betfake_outcomes'
    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey('betfake_markets.id'), nullable=False)
    outcome_name = db.Column(db.String(255), nullable=False)
    odds = db.Column(db.Integer, nullable=False) # American odds
    point_value = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    market = db.relationship('BetfakeMarket', backref=db.backref('outcomes', lazy=True))

    def __repr__(self):
        return f'<BetfakeOutcome {self.outcome_name} ({self.odds})>'

class BetfakeBet(db.Model):
    __tablename__ = 'betfake_bets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('betfake_accounts.id'), nullable=False)
    outcome_id = db.Column(db.Integer, db.ForeignKey('betfake_outcomes.id'), nullable=False)
    wager_amount = db.Column(db.Float, nullable=False)
    odds_at_time = db.Column(db.Integer, nullable=False)
    line_at_time = db.Column(db.Float, nullable=True)
    outcome_name_at_time = db.Column(db.String(255), nullable=False)
    potential_payout = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(BetStatus), nullable=False, default=BetStatus.Pending)
    placed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    settled_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('betfake_bets', lazy=True))
    account = db.relationship('BetfakeAccount', backref=db.backref('bets', lazy=True))
    outcome = db.relationship('BetfakeOutcome', backref=db.backref('bets', lazy=True))

    def __repr__(self):
        return f'<BetfakeBet {self.wager_amount} on {self.outcome_name_at_time}>'

class BetfakeTransaction(db.Model):
    __tablename__ = 'betfake_transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('betfake_accounts.id'), nullable=False)
    bet_id = db.Column(db.Integer, db.ForeignKey('betfake_bets.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.Enum(TransactionType), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('betfake_transactions', lazy=True))
    account = db.relationship('BetfakeAccount', backref=db.backref('transactions', lazy=True))
    bet = db.relationship('BetfakeBet', backref=db.backref('transactions', lazy=True))

    def __repr__(self):
        return f'<BetfakeTransaction {self.type.value} {self.amount}>'
