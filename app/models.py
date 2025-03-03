from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

from app import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(60), nullable=False, unique=True)
    password_hash = db.Column(db.String(128))
    time_zone = db.Column(db.String(50), nullable=False, default='UTC')
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
class LogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)

    actor = db.relationship('User', backref=db.backref('log_entries', lazy=True))

    def __repr__(self):
        return f'<LogEntry {self.timestamp} - {self.category}>'
    

# Add this to your existing models.py file

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    conversation_id = db.Column(db.String(36), nullable=False)  # UUID for grouping messages
    content = db.Column(db.Text, nullable=False)
    is_user = db.Column(db.Boolean, default=True)  # True if from user, False if from bot
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship back to user
    user = db.relationship('User', backref=db.backref('chat_messages', lazy=True))
    
    def __repr__(self):
        return f'<ChatMessage {self.id}: {"User" if self.is_user else "Bot"} message>'
    
    def to_dict(self):
        """Convert message to dictionary for API responses"""
        return {
            'id': self.id,
            'content': self.content,
            'is_user': self.is_user,
            'timestamp': self.timestamp.isoformat(),
            'conversation_id': self.conversation_id
        }