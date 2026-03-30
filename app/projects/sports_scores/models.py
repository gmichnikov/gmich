from datetime import datetime, timezone
from app import db


class ScoresFetchLog(db.Model):
    __tablename__ = "scores_fetch_log"

    id = db.Column(db.Integer, primary_key=True)
    sport_key = db.Column(db.String(16), nullable=False, unique=True, index=True)
    last_fetched_at = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f"<ScoresFetchLog sport={self.sport_key} last={self.last_fetched_at}>"


class ScoresGame(db.Model):
    __tablename__ = "scores_game"

    id = db.Column(db.Integer, primary_key=True)
    espn_event_id = db.Column(db.String(64), nullable=False)
    sport_key = db.Column(db.String(16), nullable=False, index=True)
    game_date = db.Column(db.Date, nullable=False, index=True)
    start_time_utc = db.Column(db.DateTime, nullable=True)
    home_team = db.Column(db.String(128), nullable=False)
    away_team = db.Column(db.String(128), nullable=False)
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    # ESPN status state: "pre", "in", "post"
    status_state = db.Column(db.String(16), nullable=False, default="pre")
    # Human-readable detail: "7:30 PM ET", "Q3 14:22", "Final"
    status_detail = db.Column(db.String(128), nullable=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint("espn_event_id", "sport_key", name="uq_scores_game_event_sport"),
    )

    def __repr__(self):
        return f"<ScoresGame {self.sport_key} {self.game_date} {self.away_team}@{self.home_team}>"
