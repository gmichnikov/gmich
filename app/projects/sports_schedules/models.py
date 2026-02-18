from datetime import datetime

from app import db


class SportsScheduleSavedQuery(db.Model):
    __tablename__ = "sports_schedule_saved_queries"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = db.Column(db.String(100), nullable=False)
    config = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.Index("ix_sports_schedule_saved_queries_user_id", "user_id"),)
