"""Places and visits for Where I've Been."""

from datetime import datetime

from app import db


class BeenPlace(db.Model):
    """A city, site, or region one user has been to."""

    __tablename__ = "been_place"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    # spot: a city or site. region: a country, state, or province with no specific site.
    kind = db.Column(db.String(16), nullable=False, default="spot")
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    country_code = db.Column(db.String(2), nullable=True)
    country_name = db.Column(db.String(128), nullable=True)
    region_name = db.Column(db.String(128), nullable=True)
    city = db.Column(db.String(128), nullable=True)
    osm_type = db.Column(db.String(8), nullable=True)
    osm_id = db.Column(db.BigInteger, nullable=True)
    osm_key = db.Column(db.String(64), nullable=True)
    osm_value = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("been_places", lazy="dynamic"))
    visits = db.relationship(
        "BeenVisit",
        back_populates="place",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.Index("ix_been_place_user_id", "user_id"),
        db.UniqueConstraint("user_id", "osm_type", "osm_id", name="uq_been_place_user_osm"),
        db.CheckConstraint("kind IN ('spot', 'region')", name="ck_been_place_kind"),
    )

    def location_label(self):
        parts = []
        for part in (self.city, self.region_name, self.country_name):
            if part and part != self.name and part not in parts:
                parts.append(part)
        return ", ".join(parts)

    def __repr__(self):
        return f"<BeenPlace {self.id}: {self.name}>"


class BeenVisit(db.Model):
    """One stay or water activity. A visit may have a place, a water body, or both."""

    __tablename__ = "been_visit"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey("been_place.id", ondelete="CASCADE"), nullable=True)
    water_slug = db.Column(db.String(64), nullable=True)
    activity = db.Column(db.String(16), nullable=True)
    visited_on = db.Column(db.Date, nullable=True)
    # year, month, or day. Null when visited_on is null.
    date_precision = db.Column(db.String(8), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship("User", backref=db.backref("been_visits", lazy="dynamic"))
    place = db.relationship("BeenPlace", back_populates="visits")

    __table_args__ = (
        db.Index("ix_been_visit_user_id", "user_id"),
        db.Index("ix_been_visit_place_id", "place_id"),
        db.CheckConstraint(
            "place_id IS NOT NULL OR water_slug IS NOT NULL",
            name="ck_been_visit_place_or_water",
        ),
        db.CheckConstraint(
            "(visited_on IS NULL AND date_precision IS NULL) OR "
            "(visited_on IS NOT NULL AND date_precision IN ('year', 'month', 'day'))",
            name="ck_been_visit_date_precision",
        ),
        db.CheckConstraint(
            "activity IS NULL OR activity IN ('swam', 'boated', 'ferry', 'dived', 'sailed')",
            name="ck_been_visit_activity",
        ),
    )

    def __repr__(self):
        return f"<BeenVisit {self.id}>"
