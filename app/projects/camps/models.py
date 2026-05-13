from app import db
from collections import Counter
from datetime import datetime, time
from typing import Optional

from sqlalchemy import Time

from app.projects.camps.session_schedule import (
    typical_inclusive_days,
    typical_week_schedule_label,
)


def _format_camp_clock_12h(t: Optional[time]) -> Optional[str]:
    """Human-readable clock like 9:00am / 3:30pm (matches previous string style)."""
    if t is None:
        return None
    hour = t.hour
    minute = t.minute
    h12 = hour % 12 or 12
    suffix = "am" if hour < 12 else "pm"
    if minute:
        return f"{h12}:{minute:02d}{suffix}"
    return f"{h12}{suffix}"

# Junction table for Camp and CampTag
camps_camp_tag = db.Table(
    "camps_camp_tag",
    db.Column("camp_id", db.Integer, db.ForeignKey("camps_camp.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("camps_tag.id"), primary_key=True),
)

class Camp(db.Model):
    __tablename__ = "camps_camp"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    website_url = db.Column(db.String(512))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(50))
    address = db.Column(db.String(255))
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(2), nullable=False, default="NJ")
    zip = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    sessions = db.relationship("CampSession", backref="camp", cascade="all, delete-orphan")
    tags = db.relationship("CampTag", secondary=camps_camp_tag, backref=db.backref("camps", lazy="dynamic"))

    @property
    def common_age_range(self):
        if not self.sessions:
            return None
        first = self.sessions[0]
        for s in self.sessions[1:]:
            if s.age_min != first.age_min or s.age_max != first.age_max:
                return None
        if first.age_min is None and first.age_max is None:
            return None
        return (first.age_min, first.age_max)

    @property
    def common_grade_range(self):
        if not self.sessions:
            return None
        first = self.sessions[0]
        for s in self.sessions[1:]:
            if s.grade_min != first.grade_min or s.grade_max != first.grade_max:
                return None
        if first.grade_min is None and first.grade_max is None:
            return None
        return (first.grade_min, first.grade_max)

    @property
    def common_price(self):
        if not self.sessions:
            return None
        first = self.sessions[0]
        for s in self.sessions[1:]:
            if s.price != first.price:
                return None
        return first.price

    @property
    def most_common_session_time_display(self):
        """
        Typical daily hours: the most frequent (start_time, end_time) pair among
        sessions that have at least one time set. Ties break lexicographically
        on the raw strings for stable display.
        """
        if not self.sessions:
            return None
        pairs = [
            (s.start_time, s.end_time)
            for s in self.sessions
            if s.start_time or s.end_time
        ]
        if not pairs:
            return None
        counts = Counter(pairs)
        best_count = max(counts.values())
        winners = [p for p, c in counts.items() if c == best_count]
        start_raw, end_raw = min(winners, key=lambda p: (p[0] or time.min, p[1] or time.min))

        fs = _format_camp_clock_12h(start_raw)
        fe = _format_camp_clock_12h(end_raw)
        if fs and fe:
            return f"{fs} – {fe}"
        if fs:
            return f"{fs} – ?"
        if fe:
            return f"? – {fe}"
        return None

    @property
    def typical_session_calendar_days(self):
        """Mode of inclusive calendar days per session (4 ≈ Mon–Thu, 5 ≈ Mon–Fri)."""
        return typical_inclusive_days(self.sessions)

    @property
    def typical_week_schedule_short(self):
        """Short label for directory cards, e.g. '4-day weeks'."""
        return typical_week_schedule_label(self.typical_session_calendar_days)

    @property
    def formatted_date_range(self):
        if not self.sessions:
            return "No sessions"
        
        sorted_sessions = sorted(self.sessions, key=lambda s: s.start_date)
        
        # Check for contiguity: gap between sessions <= 4 days (to allow for weekends + holidays)
        is_contiguous = True
        for i in range(len(sorted_sessions) - 1):
            s1 = sorted_sessions[i]
            s2 = sorted_sessions[i+1]
            gap = (s2.start_date - s1.end_date).days
            if gap > 4:
                is_contiguous = False
                break
        
        first_s = sorted_sessions[0]
        last_s = sorted_sessions[-1]

        # Always show the true overall window (first start → last end).
        span = (
            f"{first_s.start_date.strftime('%b %-d')} - {last_s.end_date.strftime('%b %-d')}"
        )
        if is_contiguous:
            return span
        # Gaps e.g. holiday week off: still show exact span, hint that weeks are spaced out.
        return f"{span} · not every week"

    @property
    def google_maps_url(self):
        if not self.address:
            # Fallback to city/state if no specific address
            query = f"{self.city}, {self.state}"
        else:
            query = f"{self.address}, {self.city}, {self.state}"
            if self.zip:
                query += f" {self.zip}"
        
        import urllib.parse
        return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}"

    def __repr__(self):
        return f"<Camp {self.name}>"

class CampSession(db.Model):
    __tablename__ = "camps_session"

    id = db.Column(db.Integer, primary_key=True)
    camp_id = db.Column(db.Integer, db.ForeignKey("camps_camp.id"), nullable=False)
    name = db.Column(db.String(255))
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(Time, nullable=True)
    end_time = db.Column(Time, nullable=True)
    age_min = db.Column(db.Integer)
    age_max = db.Column(db.Integer)
    grade_min = db.Column(db.Integer)
    grade_max = db.Column(db.Integer)
    price = db.Column(db.Numeric(10, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<CampSession {self.name} ({self.camp.name})>"

    @property
    def formatted_start_time(self):
        return _format_camp_clock_12h(self.start_time)

    @property
    def formatted_end_time(self):
        return _format_camp_clock_12h(self.end_time)

class CampTagCategory(db.Model):
    __tablename__ = "camps_tag_category"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    # Relationships
    tags = db.relationship("CampTag", backref="category", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CampTagCategory {self.name}>"

class CampTag(db.Model):
    __tablename__ = "camps_tag"

    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("camps_tag_category.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)

    __table_args__ = (db.UniqueConstraint("category_id", "name", name="uix_category_tag_name"),)

    @db.validates("name")
    def validate_name(self, key, name):
        if name:
            return name.lower().strip()
        return name

    def __repr__(self):
        return f"<CampTag {self.name} ({self.category.name})>"
