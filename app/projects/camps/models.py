from app import db
from datetime import datetime

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
        
        if is_contiguous:
            # Format like "Jun 15 - Jul 24"
            return f"{first_s.start_date.strftime('%b %-d')} - {last_s.end_date.strftime('%b %-d')}"
        else:
            # Fallback to month range like "Jun - Aug"
            return f"{first_s.start_date.strftime('%b')} - {last_s.end_date.strftime('%b')}"

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
    start_time = db.Column(db.String(50))
    end_time = db.Column(db.String(50))
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
        if not self.start_time:
            return None
        return self.start_time.lstrip('0')

    @property
    def formatted_end_time(self):
        if not self.end_time:
            return None
        return self.end_time.lstrip('0')

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
