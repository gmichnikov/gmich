from datetime import datetime

from app import db


class FriendWordleRoom(db.Model):
    __tablename__ = "friend_wordle_room"

    STATUS_WAITING = "waiting"
    STATUS_CHOOSING_ROLES = "choosing_roles"
    STATUS_SETTING_WORD = "setting_word"
    STATUS_GUESSING = "guessing"
    STATUS_WON = "won"
    STATUS_LOST = "lost"

    ROLE_SETTER = "setter"
    ROLE_GUESSER = "guesser"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False, index=True)
    seat_x = db.Column(db.String(32), nullable=True)
    seat_o = db.Column(db.String(32), nullable=True)
    name_x = db.Column(db.String(30), nullable=True)
    name_o = db.Column(db.String(30), nullable=True)
    role_x = db.Column(db.String(10), nullable=True)
    role_o = db.Column(db.String(10), nullable=True)
    secret = db.Column(db.String(5), nullable=True)
    guesses = db.Column(db.JSON, nullable=False)
    status = db.Column(db.String(20), nullable=False, default=STATUS_WAITING)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def seat_for_player(self, player_id):
        if self.seat_x and self.seat_x == player_id:
            return "X"
        if self.seat_o and self.seat_o == player_id:
            return "O"
        return None

    def role_for_seat(self, seat):
        if seat == "X":
            return self.role_x
        if seat == "O":
            return self.role_o
        return None

    def display_name(self, seat):
        raw = self.name_x if seat == "X" else self.name_o
        if raw:
            return raw
        return f"Player {seat}"

    def __repr__(self):
        return f"<FriendWordleRoom {self.code} status={self.status}>"
