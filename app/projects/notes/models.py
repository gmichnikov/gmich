from datetime import datetime

from app import db


class Note(db.Model):
    __tablename__ = 'note'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False, default='')
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    modified_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationship to User
    user = db.relationship('User', backref=db.backref('notes', lazy='dynamic'))

    # Indexes for query optimization
    __table_args__ = (
        db.Index('ix_note_user_archived_modified', 'user_id', 'is_archived', 'modified_at'),
        db.Index('ix_note_user_modified', 'user_id', 'modified_at'),
    )

    def __repr__(self):
        return f'<Note {self.id}: {self.title[:30]}>'
