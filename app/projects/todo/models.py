from app import db
from datetime import datetime

class TodoItem(db.Model):
    __tablename__ = 'todo_items'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationship to User
    user = db.relationship('User', backref=db.backref('todos', lazy=True))
    
    def __repr__(self):
        return f'<TodoItem {self.id}: {self.title}>'

