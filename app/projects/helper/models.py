from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB

from app import db


class HelperGroup(db.Model):
    __tablename__ = "helper_group"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    inbound_email = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # Relationships
    creator = db.relationship("User", foreign_keys=[created_by_user_id])
    members = db.relationship("HelperGroupMember", back_populates="group", cascade="all, delete-orphan")
    tasks = db.relationship("HelperTask", back_populates="group", cascade="all, delete-orphan")
    inbound_emails = db.relationship("HelperInboundEmail", back_populates="group")

    def __repr__(self):
        return f"<HelperGroup {self.id}: {self.name}>"


class HelperGroupMember(db.Model):
    __tablename__ = "helper_group_member"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("helper_group.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    group = db.relationship("HelperGroup", back_populates="members")
    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("group_id", "user_id", name="uix_helper_group_member_group_user"),
    )

    def __repr__(self):
        return f"<HelperGroupMember group_id={self.group_id} user_id={self.user_id}>"


class HelperInboundEmail(db.Model):
    __tablename__ = "helper_inbound_email"

    id = db.Column(db.Integer, primary_key=True)
    idempotency_key = db.Column(db.String(255), unique=True, nullable=False)
    recipient = db.Column(db.String(255), nullable=False)
    sender_raw = db.Column(db.String(255), nullable=False)
    sender_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey("helper_group.id"), nullable=True)
    subject = db.Column(db.String(500), nullable=True)
    body_text = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False)
    signature_valid = db.Column(db.Boolean, nullable=True)
    mailgun_timestamp = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    sender_user = db.relationship("User", foreign_keys=[sender_user_id])
    group = db.relationship("HelperGroup", back_populates="inbound_emails")
    action_logs = db.relationship("HelperActionLog", back_populates="inbound_email", cascade="all, delete-orphan")
    tasks = db.relationship("HelperTask", back_populates="source_inbound_email")

    __table_args__ = (
        db.Index("ix_helper_inbound_email_group_id", "group_id"),
        db.Index("ix_helper_inbound_email_status", "status"),
        db.Index("ix_helper_inbound_email_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<HelperInboundEmail {self.id}: {self.status}>"


class HelperActionLog(db.Model):
    __tablename__ = "helper_action_log"

    id = db.Column(db.Integer, primary_key=True)
    inbound_email_id = db.Column(db.Integer, db.ForeignKey("helper_inbound_email.id"), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)
    detail = db.Column(JSONB, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    inbound_email = db.relationship("HelperInboundEmail", back_populates="action_logs")

    def __repr__(self):
        return f"<HelperActionLog {self.id}: {self.action_type}>"


class HelperTask(db.Model):
    __tablename__ = "helper_task"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("helper_group.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    assignee_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="open")
    completed_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    source_inbound_email_id = db.Column(db.Integer, db.ForeignKey("helper_inbound_email.id"), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    group = db.relationship("HelperGroup", back_populates="tasks")
    assignee = db.relationship("User", foreign_keys=[assignee_user_id])
    creator = db.relationship("User", foreign_keys=[created_by_user_id])
    completer = db.relationship("User", foreign_keys=[completed_by_user_id])
    source_inbound_email = db.relationship("HelperInboundEmail", back_populates="tasks")

    __table_args__ = (
        db.Index("ix_helper_task_group_status", "group_id", "status"),
        db.Index("ix_helper_task_created_at", "created_at"),
    )

    def __repr__(self):
        return f"<HelperTask {self.id}: {self.title[:40]}>"
