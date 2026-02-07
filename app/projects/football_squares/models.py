from app import db
from datetime import datetime
import enum

class AxisType(enum.Enum):
    Draft = "Draft"
    Random = "Random"

class FootballSquaresGrid(db.Model):
    __tablename__ = 'football_squares_grids'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    share_slug = db.Column(db.String(100), unique=True, nullable=False)
    team1_name = db.Column(db.String(100), nullable=False)
    team1_color_primary = db.Column(db.String(7), nullable=False, default="#000000")
    team1_color_secondary = db.Column(db.String(7), nullable=False, default="#FFFFFF")
    team2_name = db.Column(db.String(100), nullable=False)
    team2_color_primary = db.Column(db.String(7), nullable=False, default="#000000")
    team2_color_secondary = db.Column(db.String(7), nullable=False, default="#FFFFFF")
    axis_type = db.Column(db.Enum(AxisType), nullable=False, default=AxisType.Draft)
    team1_digits = db.Column(db.String(100), nullable=False, default="0,1,2,3,4,5,6,7,8,9")
    team2_digits = db.Column(db.String(100), nullable=False, default="0,1,2,3,4,5,6,7,8,9")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('football_squares_grids', lazy=True))

    def __repr__(self):
        return f'<FootballSquaresGrid {self.name}>'

class FootballSquaresParticipant(db.Model):
    __tablename__ = 'football_squares_participants'
    id = db.Column(db.Integer, primary_key=True)
    grid_id = db.Column(db.Integer, db.ForeignKey('football_squares_grids.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    square_count = db.Column(db.Integer, nullable=False, default=0)

    grid = db.relationship('FootballSquaresGrid', backref=db.backref('participants', lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<FootballSquaresParticipant {self.name} ({self.square_count})>'

class FootballSquaresSquare(db.Model):
    __tablename__ = 'football_squares_squares'
    id = db.Column(db.Integer, primary_key=True)
    grid_id = db.Column(db.Integer, db.ForeignKey('football_squares_grids.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('football_squares_participants.id'), nullable=True)
    x_coord = db.Column(db.Integer, nullable=False) # 0-9
    y_coord = db.Column(db.Integer, nullable=False) # 0-9

    grid = db.relationship('FootballSquaresGrid', backref=db.backref('squares', lazy=True, cascade="all, delete-orphan"))
    participant = db.relationship('FootballSquaresParticipant', backref=db.backref('squares', lazy=True))

    def __repr__(self):
        return f'<FootballSquaresSquare ({self.x_coord}, {self.y_coord})>'

class FootballSquaresQuarter(db.Model):
    __tablename__ = 'football_squares_quarters'
    id = db.Column(db.Integer, primary_key=True)
    grid_id = db.Column(db.Integer, db.ForeignKey('football_squares_grids.id'), nullable=False)
    quarter_number = db.Column(db.Integer, nullable=False) # 1-4 for Q1-Q4, 5 for OT
    team1_score = db.Column(db.Integer, nullable=True)
    team2_score = db.Column(db.Integer, nullable=True)
    payout_description = db.Column(db.String(255), nullable=True)

    grid = db.relationship('FootballSquaresGrid', backref=db.backref('quarters', lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<FootballSquaresQuarter Q{self.quarter_number}>'
