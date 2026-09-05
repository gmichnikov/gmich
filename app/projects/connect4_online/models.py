from datetime import datetime

from app import db


class Connect4OnlineRoom(db.Model):
    __tablename__ = "connect4_online_room"

    STATUS_WAITING = "waiting"
    STATUS_ACTIVE = "active"
    STATUS_WON = "won"
    STATUS_DRAW = "draw"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False, index=True)
    board = db.Column(db.JSON, nullable=False)
    turn = db.Column(db.String(1), nullable=False, default="X")
    last_starter = db.Column(db.String(1), nullable=False, default="X")
    seat_x = db.Column(db.String(32), nullable=True)
    seat_o = db.Column(db.String(32), nullable=True)
    name_x = db.Column(db.String(30), nullable=True)
    name_o = db.Column(db.String(30), nullable=True)
    color_x = db.Column(db.String(16), nullable=True)
    color_o = db.Column(db.String(16), nullable=True)
    status = db.Column(db.String(10), nullable=False, default=STATUS_WAITING)
    winner = db.Column(db.String(1), nullable=True)
    winning_cells = db.Column(db.JSON, nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def seat_for_player(self, player_id):
        if self.seat_x and self.seat_x == player_id:
            return "X"
        if self.seat_o and self.seat_o == player_id:
            return "O"
        return None

    def display_name(self, seat):
        raw = self.name_x if seat == "X" else self.name_o
        if raw:
            return raw
        return f"Player {seat}"

    def __repr__(self):
        return f"<Connect4OnlineRoom {self.code} status={self.status}>"
