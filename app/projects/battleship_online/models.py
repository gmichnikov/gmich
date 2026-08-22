from datetime import datetime

from app import db


class BattleshipOnlineRoom(db.Model):
    __tablename__ = "battleship_online_room"

    STATUS_WAITING = "waiting"
    STATUS_PLACEMENT = "placement"
    STATUS_BATTLE = "battle"
    STATUS_WON = "won"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False, index=True)
    seat_x = db.Column(db.String(32), nullable=True)
    seat_o = db.Column(db.String(32), nullable=True)
    name_x = db.Column(db.String(30), nullable=True)
    name_o = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(10), nullable=False, default=STATUS_WAITING)
    turn = db.Column(db.String(1), nullable=False, default="X")
    winner = db.Column(db.String(1), nullable=True)
    fleet_x = db.Column(db.JSON, nullable=True)
    fleet_o = db.Column(db.JSON, nullable=True)
    shots_x = db.Column(db.JSON, nullable=True)
    shots_o = db.Column(db.JSON, nullable=True)
    ready_x = db.Column(db.Boolean, nullable=False, default=False)
    ready_o = db.Column(db.Boolean, nullable=False, default=False)
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
        return f"<BattleshipOnlineRoom {self.code} status={self.status}>"
