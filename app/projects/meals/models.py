"""
Meals Project Models
Database models for the Meals project
"""

from datetime import datetime
from app import db

class MealsFamilyGroup(db.Model):
    __tablename__ = 'meals_family_group'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    members = db.relationship('MealsFamilyMember', backref='family_group', lazy=True, cascade="all, delete-orphan")
    entries = db.relationship('MealsEntry', backref='family_group', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MealsFamilyGroup {self.id}: {self.name}>"

class MealsFamilyMember(db.Model):
    __tablename__ = 'meals_family_member'
    
    id = db.Column(db.Integer, primary_key=True)
    family_group_id = db.Column(db.Integer, db.ForeignKey('meals_family_group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Linked account
    display_name = db.Column(db.String(100), nullable=False) # e.g., "Dad", "Kid 1"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('meals_memberships', lazy=True))
    entries = db.relationship('MealsEntry', backref='member', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MealsFamilyMember {self.id}: {self.display_name} (group_id={self.family_group_id})>"

class MealsEntry(db.Model):
    __tablename__ = 'meals_entry'
    
    id = db.Column(db.Integer, primary_key=True)
    family_group_id = db.Column(db.Integer, db.ForeignKey('meals_family_group.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('meals_family_member.id'), nullable=False)
    
    food_name = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    meal_type = db.Column(db.String(20), nullable=False) # Breakfast, Lunch, Dinner
    date = db.Column(db.Date, nullable=False)
    
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<MealsEntry {self.id}: {self.meal_type} on {self.date} for member {self.member_id}>"
