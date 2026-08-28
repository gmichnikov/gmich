"""NFL Survivor pool models."""

from datetime import datetime

from app import db


class NflSurvivorSeason(db.Model):
    __tablename__ = "nfl_survivor_seasons"

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    # Tue boundary (US/Eastern): join closes at the first one; then every 7 days
    # pick weeks roll, picks lock, spreads assign, and odds fetch windows align.
    week_2_start = db.Column(db.DateTime(timezone=True), nullable=False)
    espn_season_year = db.Column(db.Integer, nullable=False)
    max_weeks = db.Column(db.Integer, nullable=False, default=18)
    is_active = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    participants = db.relationship(
        "NflSurvivorParticipant",
        backref="season",
        lazy=True,
        cascade="all, delete-orphan",
    )
    picks = db.relationship(
        "NflSurvivorPick",
        backref="season",
        lazy=True,
        cascade="all, delete-orphan",
    )
    weekly_results = db.relationship(
        "NflSurvivorWeeklyResult",
        backref="season",
        lazy=True,
        cascade="all, delete-orphan",
    )
    spreads = db.relationship(
        "NflSurvivorSpread",
        backref="season",
        lazy=True,
        cascade="all, delete-orphan",
    )
    games = db.relationship(
        "NflSurvivorGame",
        backref="season",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<NflSurvivorSeason {self.year}>"


class NflSurvivorParticipant(db.Model):
    __tablename__ = "nfl_survivor_participants"
    __table_args__ = (
        db.UniqueConstraint(
            "season_id", "display_name", name="uq_nfl_survivor_entry_name"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(
        db.Integer, db.ForeignKey("nfl_survivor_seasons.id"), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    has_paid = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship("User", backref=db.backref("nfl_survivor_entries", lazy=True))
    picks = db.relationship(
        "NflSurvivorPick",
        backref="participant",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<NflSurvivorParticipant {self.display_name} season={self.season_id}>"


class NflSurvivorPick(db.Model):
    __tablename__ = "nfl_survivor_picks"
    __table_args__ = (
        db.UniqueConstraint(
            "participant_id", "week", name="uq_nfl_survivor_pick"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(
        db.Integer, db.ForeignKey("nfl_survivor_seasons.id"), nullable=False
    )
    participant_id = db.Column(
        db.Integer, db.ForeignKey("nfl_survivor_participants.id"), nullable=False
    )
    week = db.Column(db.Integer, nullable=False)
    team = db.Column(db.String(64), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=True)

    def __repr__(self):
        return f"<NflSurvivorPick week={self.week} team={self.team}>"


class NflSurvivorWeeklyResult(db.Model):
    __tablename__ = "nfl_survivor_weekly_results"
    __table_args__ = (
        db.UniqueConstraint(
            "season_id", "week", "team", name="uq_nfl_survivor_weekly_result"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(
        db.Integer, db.ForeignKey("nfl_survivor_seasons.id"), nullable=False
    )
    week = db.Column(db.Integer, nullable=False)
    team = db.Column(db.String(64), nullable=False)
    result = db.Column(db.String(64), nullable=False)

    def __repr__(self):
        return f"<NflSurvivorWeeklyResult week={self.week} team={self.team}>"


class NflSurvivorSpread(db.Model):
    __tablename__ = "nfl_survivor_spreads"
    __table_args__ = (
        db.UniqueConstraint("season_id", "odds_id", name="uq_nfl_survivor_spread_odds"),
    )

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(
        db.Integer, db.ForeignKey("nfl_survivor_seasons.id"), nullable=False
    )
    odds_id = db.Column(db.String(50), nullable=False)
    update_time = db.Column(db.DateTime, nullable=False)
    game_time = db.Column(db.DateTime, nullable=False)
    home_team = db.Column(db.String(50), nullable=False)
    road_team = db.Column(db.String(50), nullable=False)
    home_team_spread = db.Column(db.Float, nullable=False)
    road_team_spread = db.Column(db.Float, nullable=False)
    week = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f"<NflSurvivorSpread week={self.week} {self.road_team}@{self.home_team}>"


class NflSurvivorGame(db.Model):
    """Kickoff time for a team in a given pool week (from ESPN)."""

    __tablename__ = "nfl_survivor_games"
    __table_args__ = (
        db.UniqueConstraint(
            "season_id", "week", "team_id", name="uq_nfl_survivor_game"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(
        db.Integer, db.ForeignKey("nfl_survivor_seasons.id"), nullable=False
    )
    week = db.Column(db.Integer, nullable=False)
    team_id = db.Column(db.String(64), nullable=False)
    kickoff = db.Column(db.DateTime, nullable=False)
    espn_event_id = db.Column(db.String(32), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<NflSurvivorGame week={self.week} team={self.team_id}>"
