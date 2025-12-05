from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
import secrets

from app import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(60), nullable=False, unique=True)
    password_hash = db.Column(db.String(128))
    time_zone = db.Column(db.String(50), nullable=False, default='UTC')
    is_admin = db.Column(db.Boolean, default=False)
    credits = db.Column(db.Integer, nullable=False, default=10)  # For Ask Many LLMs project
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
    verification_token = db.Column(db.String(100), nullable=True)
    verification_token_expiry = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_sufficient_credits(self, required_credits):
        return (self.credits or 0) >= required_credits
    
    def deduct_credits(self, amount):
        if self.has_sufficient_credits(amount):
            self.credits = (self.credits or 0) - amount
            return True
        return False
    
    def generate_verification_token(self):
        """
        Generate a new verification token and set expiry to 24 hours from now.
        Saves the token and expiry to the database.
        
        Returns:
            str: The generated verification token
        """
        # Generate a cryptographically secure random token (32 bytes = 64 hex characters)
        token = secrets.token_urlsafe(32)
        
        # Set expiry to 24 hours from now (in UTC)
        expiry = datetime.utcnow() + timedelta(hours=24)
        
        # Save to database
        self.verification_token = token
        self.verification_token_expiry = expiry
        db.session.commit()
        
        return token
    
    def is_verification_token_valid(self, token):
        """
        Check if the provided token matches and hasn't expired.
        
        Args:
            token: The verification token to check
        
        Returns:
            bool: True if token is valid and not expired, False otherwise
        """
        if not self.verification_token or not self.verification_token_expiry:
            return False
        
        # Check if token matches
        if self.verification_token != token:
            return False
        
        # Check if token hasn't expired (compare UTC times)
        if datetime.utcnow() > self.verification_token_expiry:
            return False
        
        return True
    
    def verify_email(self, token):
        """
        Verify the user's email address using the provided token.
        
        Args:
            token: The verification token
        
        Returns:
            bool: True if verification successful, False if token invalid or expired
        """
        if not self.is_verification_token_valid(token):
            return False
        
        # Mark email as verified and clear the token
        self.email_verified = True
        self.verification_token = None
        self.verification_token_expiry = None
        db.session.commit()
        
        return True
    
class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    project = db.Column(db.String(50), nullable=True)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)

    actor = db.relationship('User', backref=db.backref('log_entries', lazy=True))

    def __repr__(self):
        return f'<LogEntry {self.timestamp} - {self.project}/{self.category}>'
