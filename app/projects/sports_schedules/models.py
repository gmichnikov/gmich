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


class SportsScheduleScheduledDigest(db.Model):
    __tablename__ = "sports_schedule_scheduled_digests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    schedule_hour = db.Column(db.Integer, nullable=False)  # 5-22 (5am-10pm in 24h)
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_sent_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref="sports_schedule_digests")
    digest_queries = db.relationship(
        "SportsScheduleScheduledDigestQuery",
        backref="digest",
        cascade="all, delete-orphan",
        order_by="SportsScheduleScheduledDigestQuery.sort_order",
    )

    __table_args__ = (db.Index("ix_sports_schedule_scheduled_digests_user_id", "user_id"),)


class SportsScheduleScheduledDigestQuery(db.Model):
    __tablename__ = "sports_schedule_scheduled_digest_queries"

    id = db.Column(db.Integer, primary_key=True)
    digest_id = db.Column(
        db.Integer,
        db.ForeignKey("sports_schedule_scheduled_digests.id", ondelete="CASCADE"),
        nullable=False,
    )
    saved_query_id = db.Column(
        db.Integer,
        db.ForeignKey("sports_schedule_saved_queries.id", ondelete="CASCADE"),
        nullable=False,
    )
    sort_order = db.Column(db.Integer, default=0, nullable=False)

    saved_query = db.relationship("SportsScheduleSavedQuery", backref="digest_refs")

    __table_args__ = (
        db.UniqueConstraint("digest_id", "saved_query_id", name="uq_digest_saved_query"),
    )


class SportsScheduleZipCode(db.Model):
    __tablename__ = "ss_zip_codes"

    zip = db.Column(db.String(10), primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    state_id = db.Column(db.String(2), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)


class SportsScheduleGeocodeCache(db.Model):
    __tablename__ = "ss_geocode_cache"

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(2), nullable=False)
    lat = db.Column(db.Float, nullable=True)
    lon = db.Column(db.Float, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("city", "state", name="uq_ss_geocode_cache_city_state"),
    )
