from datetime import datetime

from app import db


class Reminder(db.Model):
    __tablename__ = "reminder"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=True)
    remind_at = db.Column(db.DateTime, nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("reminders", lazy="dynamic"))

    __table_args__ = (
        db.Index("ix_reminder_user_remind_at", "user_id", "remind_at"),
    )

    def __repr__(self):
        return f"<Reminder {self.id}: {self.title[:40]}>"
