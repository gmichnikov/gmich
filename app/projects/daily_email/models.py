from datetime import datetime

from app import db


class DailyEmailProfile(db.Model):
    __tablename__ = "daily_email_profile"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    digest_enabled = db.Column(db.Boolean, nullable=False, default=False)
    send_hour_local = db.Column(db.Integer, nullable=False, default=6)
    include_weather = db.Column(db.Boolean, nullable=False, default=True)
    include_stocks = db.Column(db.Boolean, nullable=False, default=True)
    include_sports = db.Column(db.Boolean, nullable=False, default=True)
    include_jobs = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref=db.backref("daily_email_profile", uselist=False))

    def __repr__(self):
        return f"<DailyEmailProfile user_id={self.user_id} enabled={self.digest_enabled}>"


class DailyEmailWeatherLocation(db.Model):
    __tablename__ = "daily_email_weather_location"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    display_label = db.Column(db.String(100), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship(
        "User", backref=db.backref("daily_email_weather_locations", lazy="dynamic")
    )

    __table_args__ = (
        db.Index("ix_daily_email_weather_location_user_id", "user_id"),
    )

    def __repr__(self):
        return f"<DailyEmailWeatherLocation user_id={self.user_id} label={self.display_label!r}>"


class DailyEmailStockTicker(db.Model):
    __tablename__ = "daily_email_stock_ticker"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    symbol = db.Column(db.String(20), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship(
        "User", backref=db.backref("daily_email_stock_tickers", lazy="dynamic")
    )

    __table_args__ = (
        db.Index("ix_daily_email_stock_ticker_user_id", "user_id"),
    )

    def __repr__(self):
        return f"<DailyEmailStockTicker user_id={self.user_id} symbol={self.symbol}>"


class DailyEmailSportsWatch(db.Model):
    __tablename__ = "daily_email_sports_watch"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    league_code = db.Column(db.String(10), nullable=False)
    espn_team_id = db.Column(db.String(20), nullable=False)
    team_display_name = db.Column(db.String(80), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship(
        "User", backref=db.backref("daily_email_sports_watches", lazy="dynamic")
    )

    __table_args__ = (
        db.Index("ix_daily_email_sports_watch_user_id", "user_id"),
    )

    def __repr__(self):
        return (
            f"<DailyEmailSportsWatch user_id={self.user_id} "
            f"league={self.league_code} team={self.team_display_name!r}>"
        )


class DailyEmailJobsConfig(db.Model):
    __tablename__ = "daily_email_jobs_config"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    ashby_slug = db.Column(db.String(255), nullable=True)
    filter_phrase = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref=db.backref("daily_email_jobs_config", uselist=False))

    def __repr__(self):
        return f"<DailyEmailJobsConfig user_id={self.user_id} slug={self.ashby_slug!r}>"


class DailyEmailSendLog(db.Model):
    __tablename__ = "daily_email_send_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    digest_local_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # sent | failed | no_credits | pending
    modules_included = db.Column(db.String(100), nullable=True)
    error_summary = db.Column(db.String(500), nullable=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship(
        "User", backref=db.backref("daily_email_send_logs", lazy="dynamic")
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "digest_local_date", name="uix_daily_email_send_log_user_date"
        ),
        db.Index("ix_daily_email_send_log_user_id", "user_id"),
    )

    def __repr__(self):
        return (
            f"<DailyEmailSendLog user_id={self.user_id} "
            f"date={self.digest_local_date} status={self.status}>"
        )
