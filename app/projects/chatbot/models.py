from datetime import datetime
from app import db


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

