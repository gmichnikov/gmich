"""Kalshi races, candidate markets, and the prices we poll over time.

Office, state, and party are filled in when the market gives us enough to
derive them. Other markets can omit them.
"""

from datetime import datetime, timezone

from app import db


def _utcnow():
    return datetime.now(timezone.utc)


class Election2026Race(db.Model):
    """One Kalshi event, such as the Michigan Senate field."""

    __tablename__ = "election2026_race"

    id = db.Column(db.Integer, primary_key=True)
    event_ticker = db.Column(db.String(160), nullable=False, unique=True, index=True)
    series_ticker = db.Column(db.String(160), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    subtitle = db.Column(db.String(500), nullable=True)
    # Kalshi category, e.g. "Elections". Not a structured "politics" flag.
    category = db.Column(db.String(64), nullable=True, index=True)
    tags = db.Column(db.JSON, nullable=True)
    mutually_exclusive = db.Column(db.Boolean, nullable=True)
    # Derived by us. Null when the event is not a statewide office.
    office = db.Column(db.String(32), nullable=True, index=True)
    state = db.Column(db.String(32), nullable=True, index=True)
    # When the underlying event happens. Kalshi occurrence time, not the
    # later certification expiration. Null when the market has no such time.
    occurs_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    markets = db.relationship(
        "Election2026Market",
        back_populates="race",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Election2026Race {self.event_ticker}>"


class Election2026Market(db.Model):
    """One Kalshi contract, usually a single candidate."""

    __tablename__ = "election2026_market"

    id = db.Column(db.Integer, primary_key=True)
    race_id = db.Column(
        db.Integer,
        db.ForeignKey("election2026_race.id"),
        nullable=False,
        index=True,
    )
    ticker = db.Column(db.String(160), nullable=False, unique=True, index=True)
    # Question text. Candidate name and party are separate and optional.
    title = db.Column(db.String(500), nullable=False)
    candidate_name = db.Column(db.String(200), nullable=True)
    party = db.Column(db.String(64), nullable=True, index=True)
    status = db.Column(db.String(32), nullable=True)
    # Empty until Kalshi settles the contract.
    result = db.Column(db.String(16), nullable=True)
    rules_primary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    race = db.relationship("Election2026Race", back_populates="markets")
    prices = db.relationship(
        "Election2026Price",
        back_populates="market",
        cascade="all, delete-orphan",
        order_by="Election2026Price.observed_at",
    )

    def __repr__(self):
        return f"<Election2026Market {self.ticker}>"


class Election2026Price(db.Model):
    """One poll of a market. Bid and ask are the live quote; last trade can lag."""

    __tablename__ = "election2026_price"

    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(
        db.Integer,
        db.ForeignKey("election2026_market.id"),
        nullable=False,
        index=True,
    )
    observed_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    yes_bid = db.Column(db.Numeric(18, 6), nullable=True)
    yes_ask = db.Column(db.Numeric(18, 6), nullable=True)
    last_price = db.Column(db.Numeric(18, 6), nullable=True)
    yes_bid_size = db.Column(db.Numeric(18, 6), nullable=True)
    yes_ask_size = db.Column(db.Numeric(18, 6), nullable=True)
    volume = db.Column(db.Numeric(18, 6), nullable=True)
    volume_24h = db.Column(db.Numeric(18, 6), nullable=True)
    open_interest = db.Column(db.Numeric(18, 6), nullable=True)

    market = db.relationship("Election2026Market", back_populates="prices")

    __table_args__ = (
        db.UniqueConstraint(
            "market_id",
            "observed_at",
            name="uq_election2026_price_market_observed",
        ),
    )

    def __repr__(self):
        return f"<Election2026Price market_id={self.market_id} at={self.observed_at}>"
