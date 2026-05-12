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

    def __repr__(self):
        return f"<CampTag {self.name} ({self.category.name})>"
