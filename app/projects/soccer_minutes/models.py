"""
Soccer Minutes models (v1 schema).

Formation lives on the game as the source of truth. A team holds a default
template that is copied onto each new game at creation.

See docs/PRD.md and docs/DATA_MODEL.md before running migrations.
"""

from datetime import date, datetime
import copy

from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.projects.soccer_minutes.formation_config import (
    DEFAULT_PERIOD_COUNT,
    default_formation,
)


class ScmTeam(db.Model):
    """One squad for one season, owned by a user. Holds the roster and defaults."""

    __tablename__ = "scm_team"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    season_label = db.Column(db.String(80), nullable=True)
    period_count = db.Column(
        db.Integer, nullable=False, default=DEFAULT_PERIOD_COUNT
    )
    formation = db.Column(JSONB, nullable=False, default=lambda: default_formation())
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref=db.backref("scm_teams", lazy="dynamic"))
    players = db.relationship(
        "ScmPlayer",
        back_populates="team",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ScmPlayer.sort_order",
    )
    games = db.relationship(
        "ScmGame",
        back_populates="team",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="ScmGame.game_date.desc()",
    )

    __table_args__ = (db.Index("ix_scm_team_user_id", "user_id"),)

    @property
    def display_name(self):
        if self.season_label:
            return f"{self.name} — {self.season_label}"
        return self.name

    def __repr__(self):
        return f"<ScmTeam {self.id}: {self.name}>"


class ScmPlayer(db.Model):
    """A player on a team's roster."""

    __tablename__ = "scm_player"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(
        db.Integer, db.ForeignKey("scm_team.id", ondelete="CASCADE"), nullable=False
    )
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    jersey_number = db.Column(db.String(8), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    team = db.relationship("ScmTeam", back_populates="players")

    __table_args__ = (db.Index("ix_scm_player_team_id", "team_id"),)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self):
        return f"<ScmPlayer {self.id}: {self.full_name}>"


class ScmGame(db.Model):
    """
    One game: date, opponent, copied formation, live clock, and draft field.

    ``formation`` and ``draft_assignments`` are JSON; assign a new dict when
    saving. Plain JSONB columns do not track in-place mutation.
    """

    __tablename__ = "scm_game"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(
        db.Integer, db.ForeignKey("scm_team.id", ondelete="CASCADE"), nullable=False
    )
    game_date = db.Column(db.Date, nullable=False, default=date.today)
    opponent_name = db.Column(db.String(120), nullable=False)
    period_count = db.Column(
        db.Integer, nullable=False, default=DEFAULT_PERIOD_COUNT
    )
    formation = db.Column(JSONB, nullable=False, default=lambda: default_formation())
    draft_assignments = db.Column(JSONB, nullable=False, default=dict)
    pending_assignments = db.Column(JSONB, nullable=True)
    current_period = db.Column(db.Integer, nullable=False, default=1)
    clock_running = db.Column(db.Boolean, nullable=False, default=False)
    elapsed_ms = db.Column(db.Integer, nullable=False, default=0)
    last_resumed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    team = db.relationship("ScmTeam", back_populates="games")
    roster_entries = db.relationship(
        "ScmGameRosterEntry",
        back_populates="game",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    events = db.relationship(
        "ScmEvent",
        back_populates="game",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (db.Index("ix_scm_game_team_id", "team_id"),)

    @classmethod
    def from_team_defaults(cls, team, game_date, opponent_name):
        return cls(
            team_id=team.id,
            game_date=game_date,
            opponent_name=opponent_name,
            period_count=team.period_count,
            formation=copy.deepcopy(team.formation or default_formation()),
            draft_assignments={},
        )

    def __repr__(self):
        return f"<ScmGame {self.id}: team={self.team_id} date={self.game_date}>"


class ScmGameRosterEntry(db.Model):
    """Per-game absence. A player is present unless a row exists with is_present=False."""

    __tablename__ = "scm_game_roster_entry"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(
        db.Integer, db.ForeignKey("scm_game.id", ondelete="CASCADE"), nullable=False
    )
    player_id = db.Column(
        db.Integer, db.ForeignKey("scm_player.id", ondelete="CASCADE"), nullable=False
    )
    is_present = db.Column(db.Boolean, nullable=False, default=True)

    game = db.relationship("ScmGame", back_populates="roster_entries")
    player = db.relationship("ScmPlayer")

    __table_args__ = (
        db.UniqueConstraint(
            "game_id", "player_id", name="uq_scm_game_roster_entry_game_player"
        ),
        db.Index("ix_scm_game_roster_entry_game_id", "game_id"),
    )

    def __repr__(self):
        status = "present" if self.is_present else "absent"
        return (
            f"<ScmGameRosterEntry game={self.game_id} "
            f"player={self.player_id} {status}>"
        )


class ScmEvent(db.Model):
    """One period_start, field_set, or period_end in a game."""

    __tablename__ = "scm_event"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(
        db.Integer, db.ForeignKey("scm_game.id", ondelete="CASCADE"), nullable=False
    )
    period = db.Column(db.Integer, nullable=False)
    at_ms = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(20), nullable=False)
    payload = db.Column(JSONB, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    game = db.relationship("ScmGame", back_populates="events")

    __table_args__ = (db.Index("ix_scm_event_game_id", "game_id"),)

    def __repr__(self):
        return (
            f"<ScmEvent game={self.game_id} period={self.period} "
            f"type={self.type} at_ms={self.at_ms}>"
        )
