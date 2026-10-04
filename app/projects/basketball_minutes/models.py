"""
Basketball Minutes models.

Clean 5x5 lineup tracking with no positions. Time is scoreboard countdown.
"""

from datetime import date, datetime
import copy

from sqlalchemy.dialects.postgresql import JSONB

from app import db

DEFAULT_PERIOD_COUNT = 4
DEFAULT_PERIOD_MINUTES = 8


class BkmTeam(db.Model):
    """One basketball squad for one season, owned by a user."""

    __tablename__ = "bkm_team"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    season_label = db.Column(db.String(80), nullable=True)
    default_period_count = db.Column(
        db.Integer, nullable=False, default=DEFAULT_PERIOD_COUNT
    )
    default_period_minutes = db.Column(
        db.Integer, nullable=False, default=DEFAULT_PERIOD_MINUTES
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref=db.backref("bkm_teams", lazy="dynamic"))
    players = db.relationship(
        "BkmPlayer",
        back_populates="team",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="BkmPlayer.sort_order",
    )
    games = db.relationship(
        "BkmGame",
        back_populates="team",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="BkmGame.game_date.desc()",
    )

    __table_args__ = (db.Index("ix_bkm_team_user_id", "user_id"),)

    @property
    def display_name(self):
        if self.season_label:
            return f"{self.name} — {self.season_label}"
        return self.name

    def __repr__(self):
        return f"<BkmTeam {self.id}: {self.name}>"


class BkmPlayer(db.Model):
    """A player on a team's roster."""

    __tablename__ = "bkm_player"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(
        db.Integer, db.ForeignKey("bkm_team.id", ondelete="CASCADE"), nullable=False
    )
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    jersey_number = db.Column(db.String(8), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    team = db.relationship("BkmTeam", back_populates="players")

    __table_args__ = (db.Index("ix_bkm_player_team_id", "team_id"),)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_label(self):
        jersey = f"#{self.jersey_number} " if self.jersey_number else ""
        return f"{jersey}{self.full_name}"

    def __repr__(self):
        return f"<BkmPlayer {self.id}: {self.full_name}>"


class BkmGame(db.Model):
    """
    One game: date, opponent, period format, starting lineup, and final scores.

    ``draft_lineup`` and ``pending_lineup`` are JSON lists of player IDs (up to 5).
    """

    __tablename__ = "bkm_game"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(
        db.Integer, db.ForeignKey("bkm_team.id", ondelete="CASCADE"), nullable=False
    )
    game_date = db.Column(db.Date, nullable=False, default=date.today)
    opponent_name = db.Column(db.String(120), nullable=False)
    period_count = db.Column(
        db.Integer, nullable=False, default=DEFAULT_PERIOD_COUNT
    )
    period_minutes = db.Column(
        db.Integer, nullable=False, default=DEFAULT_PERIOD_MINUTES
    )
    current_period = db.Column(db.Integer, nullable=False, default=1)
    
    # draft_lineup is a list of player_ids for pre-game or between-periods
    draft_lineup = db.Column(JSONB, nullable=False, default=list)
    # pending_lineup is a staged 5-player list of player_ids during live play
    pending_lineup = db.Column(JSONB, nullable=True)

    # Final score overrides/entries
    final_our_score = db.Column(db.Integer, nullable=True)
    final_opponent_score = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    team = db.relationship("BkmTeam", back_populates="games")
    roster_entries = db.relationship(
        "BkmGameRosterEntry",
        back_populates="game",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    events = db.relationship(
        "BkmEvent",
        back_populates="game",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="BkmEvent.id",
    )

    __table_args__ = (db.Index("ix_bkm_game_team_id", "team_id"),)

    @classmethod
    def from_team_defaults(cls, team, game_date, opponent_name, period_count=None, period_minutes=None):
        return cls(
            team_id=team.id,
            game_date=game_date,
            opponent_name=opponent_name,
            period_count=period_count if period_count is not None else team.default_period_count,
            period_minutes=period_minutes if period_minutes is not None else team.default_period_minutes,
            draft_lineup=[],
        )

    def __repr__(self):
        return f"<BkmGame {self.id}: team={self.team_id} date={self.game_date}>"


class BkmGameRosterEntry(db.Model):
    """Per-game absence. A player is present unless is_present=False."""

    __tablename__ = "bkm_game_roster_entry"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(
        db.Integer, db.ForeignKey("bkm_game.id", ondelete="CASCADE"), nullable=False
    )
    player_id = db.Column(
        db.Integer, db.ForeignKey("bkm_player.id", ondelete="CASCADE"), nullable=False
    )
    is_present = db.Column(db.Boolean, nullable=False, default=True)

    game = db.relationship("BkmGame", back_populates="roster_entries")
    player = db.relationship("BkmPlayer")

    __table_args__ = (
        db.UniqueConstraint(
            "game_id", "player_id", name="uq_bkm_game_roster_entry_game_player"
        ),
        db.Index("ix_bkm_game_roster_entry_game_id", "game_id"),
    )

    def __repr__(self):
        status = "present" if self.is_present else "absent"
        return f"<BkmGameRosterEntry game={self.game_id} player={self.player_id} {status}>"


class BkmEvent(db.Model):
    """
    Append-only log of events for a game.
    Types:
    - 'period_start': payload: {'lineup': [ids], 'period_seconds': total_sec}
    - 'sub': remaining_seconds: X, payload: {'lineup': [ids], 'on': [ids], 'off': [ids]}
    - 'score': remaining_seconds: X (or 0), payload: {'player_id': id, 'shot_type': '1pt'|'2pt'|'3pt'|'miss_ft', 'points': 1|2|3|0}
    - 'period_end': remaining_seconds: 0 (or X), payload: {}
    """

    __tablename__ = "bkm_event"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(
        db.Integer, db.ForeignKey("bkm_game.id", ondelete="CASCADE"), nullable=False
    )
    period = db.Column(db.Integer, nullable=False)
    remaining_seconds = db.Column(db.Integer, nullable=False, default=0)
    event_type = db.Column(db.String(30), nullable=False)
    payload = db.Column(JSONB, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    game = db.relationship("BkmGame", back_populates="events")

    __table_args__ = (db.Index("ix_bkm_event_game_id", "game_id"),)

    def __repr__(self):
        return (
            f"<BkmEvent game={self.game_id} period={self.period} "
            f"type={self.event_type} rem_sec={self.remaining_seconds}>"
        )
