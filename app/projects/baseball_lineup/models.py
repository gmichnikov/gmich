"""
Baseball Lineup models (v1 schema).

Lineup structure lives on the game, which is the source of truth. A team holds a
default template that is copied onto each new game at creation, so there is no
inheritance to resolve at read time.

See docs/PRD.md and docs/DATA_MODEL.md before running migrations.
"""

from datetime import date, datetime

from sqlalchemy.dialects.postgresql import JSONB

from app import db
from app.projects.baseball_lineup.lineup_config import (
    DEFAULT_INNING_COUNT,
    default_expected_counts,
)


class BluTeam(db.Model):
    """One squad for one season, owned by a user. Holds the roster and defaults."""

    __tablename__ = "blu_team"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    season_label = db.Column(db.String(80), nullable=True)
    default_inning_count = db.Column(
        db.Integer, nullable=False, default=DEFAULT_INNING_COUNT
    )
    default_expected_counts = db.Column(
        JSONB, nullable=False, default=lambda: default_expected_counts()
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref=db.backref("blu_teams", lazy="dynamic"))
    players = db.relationship(
        "BluPlayer",
        back_populates="team",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="BluPlayer.sort_order",
    )
    games = db.relationship(
        "BluGame",
        back_populates="team",
        lazy="dynamic",
        cascade="all, delete-orphan",
        order_by="BluGame.game_date.desc()",
    )

    __table_args__ = (db.Index("ix_blu_team_user_id", "user_id"),)

    @property
    def display_name(self):
        if self.season_label:
            return f"{self.name} — {self.season_label}"
        return self.name

    def __repr__(self):
        return f"<BluTeam {self.id}: {self.name}>"


class BluPlayer(db.Model):
    """A player on a team's roster."""

    __tablename__ = "blu_player"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(
        db.Integer, db.ForeignKey("blu_team.id", ondelete="CASCADE"), nullable=False
    )
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    team = db.relationship("BluTeam", back_populates="players")

    __table_args__ = (db.Index("ix_blu_player_team_id", "team_id"),)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self):
        return f"<BluPlayer {self.id}: {self.full_name}>"


class BluGame(db.Model):
    """
    One game: date, opponent, and its own lineup structure.

    ``expected_counts`` maps position code -> list of expected counts indexed by
    inning (index 0 is inning 1). Assign a new dict when saving; plain JSONB
    columns do not track in-place mutation.
    """

    __tablename__ = "blu_game"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(
        db.Integer, db.ForeignKey("blu_team.id", ondelete="CASCADE"), nullable=False
    )
    game_date = db.Column(db.Date, nullable=False, default=date.today)
    opponent_name = db.Column(db.String(120), nullable=False)
    inning_count = db.Column(db.Integer, nullable=False, default=DEFAULT_INNING_COUNT)
    expected_counts = db.Column(
        JSONB, nullable=False, default=lambda: default_expected_counts()
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    team = db.relationship("BluTeam", back_populates="games")
    roster_entries = db.relationship(
        "BluGameRosterEntry",
        back_populates="game",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    lineup_cells = db.relationship(
        "BluLineupCell",
        back_populates="game",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (db.Index("ix_blu_game_team_id", "team_id"),)

    @classmethod
    def from_team_defaults(cls, team, game_date, opponent_name):
        """Create a game with the team's structure copied onto it."""
        return cls(
            team_id=team.id,
            game_date=game_date,
            opponent_name=opponent_name,
            inning_count=team.default_inning_count,
            expected_counts=dict(team.default_expected_counts or {}),
        )

    def __repr__(self):
        return f"<BluGame {self.id}: team={self.team_id} date={self.game_date}>"


class BluGameRosterEntry(db.Model):
    """
    Per-game exceptions for one player: absence and batting order.

    Rows are optional. A player is present unless a row exists with
    ``is_present = False``, which is why roster additions show up in every game
    without a sync step.
    """

    __tablename__ = "blu_game_roster_entry"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(
        db.Integer, db.ForeignKey("blu_game.id", ondelete="CASCADE"), nullable=False
    )
    player_id = db.Column(
        db.Integer, db.ForeignKey("blu_player.id", ondelete="CASCADE"), nullable=False
    )
    is_present = db.Column(db.Boolean, nullable=False, default=True)
    batting_order = db.Column(db.Integer, nullable=True)

    game = db.relationship("BluGame", back_populates="roster_entries")
    player = db.relationship("BluPlayer")

    __table_args__ = (
        db.UniqueConstraint(
            "game_id", "player_id", name="uq_blu_game_roster_entry_game_player"
        ),
        db.Index("ix_blu_game_roster_entry_game_id", "game_id"),
    )

    def __repr__(self):
        status = "present" if self.is_present else "absent"
        return (
            f"<BluGameRosterEntry game={self.game_id} "
            f"player={self.player_id} {status}>"
        )


class BluLineupCell(db.Model):
    """
    One cell in the lineup grid: player x inning -> position code.

    Multiple players may share a position in one inning (e.g. two CF); counts are
    checked against the game's expected_counts instead. A missing cell for a
    present player is a Blank in the UI.
    """

    __tablename__ = "blu_lineup_cell"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(
        db.Integer, db.ForeignKey("blu_game.id", ondelete="CASCADE"), nullable=False
    )
    player_id = db.Column(
        db.Integer, db.ForeignKey("blu_player.id", ondelete="CASCADE"), nullable=False
    )
    inning = db.Column(db.Integer, nullable=False)
    position_code = db.Column(db.String(20), nullable=False)

    game = db.relationship("BluGame", back_populates="lineup_cells")
    player = db.relationship("BluPlayer")

    __table_args__ = (
        db.UniqueConstraint(
            "game_id", "player_id", "inning", name="uq_blu_lineup_cell_game_player_inning"
        ),
        db.Index("ix_blu_lineup_cell_game_id", "game_id"),
    )

    def __repr__(self):
        return (
            f"<BluLineupCell game={self.game_id} player={self.player_id} "
            f"inning={self.inning} pos={self.position_code}>"
        )
