from datetime import datetime

from app import db


class BowlingGame(db.Model):
    __tablename__ = "bowling_game"

    STATUS_SETUP = "setup"
    STATUS_ACTIVE = "active"
    STATUS_COMPLETE = "complete"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_SETUP)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    players = db.relationship(
        "BowlingPlayer",
        backref="game",
        cascade="all, delete-orphan",
        order_by="BowlingPlayer.order_index",
    )

    def __repr__(self):
        return f"<BowlingGame code={self.code} status={self.status}>"


class BowlingPlayer(db.Model):
    __tablename__ = "bowling_player"

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey("bowling_game.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    order_index = db.Column(db.Integer, nullable=False, default=0)

    rolls = db.relationship(
        "BowlingRoll",
        backref="player",
        cascade="all, delete-orphan",
        order_by="BowlingRoll.frame, BowlingRoll.roll",
    )

    def __repr__(self):
        return f"<BowlingPlayer {self.name!r} game_id={self.game_id}>"


class BowlingRoll(db.Model):
    __tablename__ = "bowling_roll"

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey("bowling_player.id"), nullable=False)
    frame = db.Column(db.Integer, nullable=False)
    roll = db.Column(db.Integer, nullable=False)
    pins = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "player_id",
            "frame",
            "roll",
            name="uq_bowling_roll_player_frame_roll",
        ),
    )

    def __repr__(self):
        return f"<BowlingRoll player_id={self.player_id} f={self.frame} r={self.roll} pins={self.pins}>"
