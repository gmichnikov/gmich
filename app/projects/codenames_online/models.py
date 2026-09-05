from datetime import datetime

from app import db


class CodenamesOnlineRoom(db.Model):
    __tablename__ = "codenames_online_room"

    STATUS_WAITING_DEVICES = "waiting_devices"
    STATUS_WAITING_ROLES = "waiting_roles"
    STATUS_WAITING_START = "waiting_start"
    STATUS_PREVIEW = "preview"
    STATUS_ACTIVE = "active"
    STATUS_WON = "won"

    ROLE_CLUE_GIVER = "clue_giver"
    ROLE_GUESSER = "guesser"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False, index=True)
    seat_x = db.Column(db.String(32), nullable=True)
    seat_o = db.Column(db.String(32), nullable=True)
    phone_role_x = db.Column(db.String(12), nullable=True)
    phone_role_o = db.Column(db.String(12), nullable=True)
    word_list_id = db.Column(db.String(32), nullable=True)
    exclude_confusing = db.Column(db.Boolean, nullable=False, default=True)
    name_red = db.Column(db.String(30), nullable=True)
    name_blue = db.Column(db.String(30), nullable=True)
    words = db.Column(db.JSON, nullable=True)
    key = db.Column(db.JSON, nullable=True)
    revealed = db.Column(db.JSON, nullable=True)
    turn = db.Column(db.String(5), nullable=True)
    winner = db.Column(db.String(5), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_WAITING_DEVICES)
    version = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def seat_for_player(self, player_id):
        if self.seat_x and self.seat_x == player_id:
            return "X"
        if self.seat_o and self.seat_o == player_id:
            return "O"
        return None

    def phone_role_for_seat(self, seat):
        if seat == "X":
            return self.phone_role_x
        if seat == "O":
            return self.phone_role_o
        return None

    def clue_giver_seat(self):
        if self.phone_role_x == self.ROLE_CLUE_GIVER:
            return "X"
        if self.phone_role_o == self.ROLE_CLUE_GIVER:
            return "O"
        return None

    def guesser_seat(self):
        if self.phone_role_x == self.ROLE_GUESSER:
            return "X"
        if self.phone_role_o == self.ROLE_GUESSER:
            return "O"
        return None

    def both_seats_filled(self):
        return self.seat_x is not None and self.seat_o is not None

    def roles_assigned(self):
        return (
            self.phone_role_x in (self.ROLE_CLUE_GIVER, self.ROLE_GUESSER)
            and self.phone_role_o in (self.ROLE_CLUE_GIVER, self.ROLE_GUESSER)
            and self.phone_role_x != self.phone_role_o
        )

    def spymaster_name(self, team_color):
        if team_color == "red":
            return self.name_red or "Red spymaster"
        if team_color == "blue":
            return self.name_blue or "Blue spymaster"
        return team_color

    def __repr__(self):
        return f"<CodenamesOnlineRoom {self.code} status={self.status}>"


class CodenamesConfusingWord(db.Model):
    __tablename__ = "codenames_confusing_word"

    word = db.Column(db.String(64), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    creator = db.relationship("User", foreign_keys=[created_by_user_id])
