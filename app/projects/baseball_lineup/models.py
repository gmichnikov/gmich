"""
Baseball Lineup models (v1 schema).

See docs/PRD.md and docs/DATA_MODEL.md before running migrations.
"""

from datetime import date, datetime

from sqlalchemy.dialects.postgresql import JSONB

from app import db


class BluTeam(db.Model):
    """A youth baseball team owned by a user."""

    __tablename__ = "blu_team"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    season_label = db.Column(db.String(80), nullable=True)
    default_inning_count = db.Column(db.Integer, nullable=False, default=6)
    settings = db.Column(JSONB, nullable=False, default=dict)
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
    """One game for a team (date + opponent)."""

    __tablename__ = "blu_game"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(
        db.Integer, db.ForeignKey("blu_team.id", ondelete="CASCADE"), nullable=False
    )
    game_date = db.Column(db.Date, nullable=False, default=date.today)
    opponent_name = db.Column(db.String(120), nullable=False)
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

    def __repr__(self):
        return f"<BluGame {self.id}: team={self.team_id} date={self.game_date}>"


class BluGameRosterEntry(db.Model):
    """Which roster players are present for a given game."""

    __tablename__ = "blu_game_roster_entry"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(
        db.Integer, db.ForeignKey("blu_game.id", ondelete="CASCADE"), nullable=False
    )
    player_id = db.Column(
        db.Integer, db.ForeignKey("blu_player.id", ondelete="CASCADE"), nullable=False
    )
    is_present = db.Column(db.Boolean, nullable=False, default=True)

    game = db.relationship("BluGame", back_populates="roster_entries")
    player = db.relationship("BluPlayer")

    __table_args__ = (
        db.UniqueConstraint("game_id", "player_id", name="uq_blu_game_roster_entry_game_player"),
        db.Index("ix_blu_game_roster_entry_game_id", "game_id"),
    )

    def __repr__(self):
        status = "present" if self.is_present else "absent"
        return f"<BluGameRosterEntry game={self.game_id} player={self.player_id} {status}>"


class BluLineupCell(db.Model):
    """
    One cell in the lineup grid: player × inning → position code.

    Multiple players may share the same position in one inning (e.g. two CF).
    Missing cell for a present player × inning = Blank in the UI.
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
