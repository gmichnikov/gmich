from datetime import datetime

from app import db
from app.projects.checkers_online.cpu import CPU_DISPLAY_NAME, CPU_PLAYER_ID


class CheckersOnlineRoom(db.Model):
    __tablename__ = "checkers_online_room"

    STATUS_WAITING = "waiting"
    STATUS_ACTIVE = "active"
    STATUS_WON = "won"
    STATUS_DRAW = "draw"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False, index=True)
    board = db.Column(db.JSON, nullable=False)
    turn = db.Column(db.String(5), nullable=False, default="black")
    last_starter = db.Column(db.String(5), nullable=False, default="black")
    seat_x = db.Column(db.String(32), nullable=True)
    seat_o = db.Column(db.String(32), nullable=True)
    name_x = db.Column(db.String(30), nullable=True)
    name_o = db.Column(db.String(30), nullable=True)
    color_x = db.Column(db.String(5), nullable=False, default="black")
    color_o = db.Column(db.String(5), nullable=False, default="red")
    status = db.Column(db.String(10), nullable=False, default=STATUS_WAITING)
    winner = db.Column(db.String(5), nullable=True)
    result_reason = db.Column(db.String(20), nullable=True)
    quiet_plies = db.Column(db.Integer, nullable=False, default=0)
    position_history = db.Column(db.JSON, nullable=False)
    vs_cpu = db.Column(db.Boolean, nullable=False, default=False)
    difficulty = db.Column(db.String(10), nullable=False, default="medium")
    cpu_first = db.Column(db.Boolean, nullable=False, default=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def seat_for_player(self, player_id):
        if self.seat_x and self.seat_x == player_id:
            return "X"
        if self.seat_o and self.seat_o == player_id:
            return "O"
        return None

    def color_for_seat(self, seat):
        if seat == "X":
            return self.color_x
        if seat == "O":
            return self.color_o
        return None

    def display_name(self, seat):
        seat_id = self.seat_x if seat == "X" else self.seat_o
        if seat_id == CPU_PLAYER_ID:
            return CPU_DISPLAY_NAME
        raw = self.name_x if seat == "X" else self.name_o
        if raw:
            return raw
        return f"Player {seat}"

    def __repr__(self):
        return f"<CheckersOnlineRoom {self.code} status={self.status}>"
