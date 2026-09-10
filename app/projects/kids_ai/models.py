"""Kids AI v1 schema. See docs/DATA_MODEL.md. Do not put children on ``user``."""

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class KidsAiParent(db.Model):
    """Hub user allowlisted as a Kids AI parent."""

    __tablename__ = "kids_ai_parent"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )

    user = db.relationship("User", foreign_keys=[user_id])
    created_by = db.relationship("User", foreign_keys=[created_by_user_id])


class KidsAiChild(db.Model):
    """Kids AI-only login. Not a hub User."""

    __tablename__ = "kids_ai_child"

    AGE_YOUNG_CHILD = "young_child"
    AGE_TWEEN = "tween"
    AGE_TEEN = "teen"
    AGE_TIERS = (AGE_YOUNG_CHILD, AGE_TWEEN, AGE_TEEN)

    id = db.Column(db.Integer, primary_key=True)
    parent_user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    username = db.Column(db.String(20), nullable=False, unique=True)
    password_hash = db.Column(db.String(256), nullable=False)
    display_name = db.Column(db.String(50), nullable=False)
    age_tier = db.Column(db.String(20), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    lock_count = db.Column(db.Integer, nullable=False, default=0)
    paused = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    parent = db.relationship("User", foreign_keys=[parent_user_id])
    conversations = db.relationship(
        "KidsAiConversation",
        back_populates="child",
        cascade="all, delete-orphan",
    )
    consent_events = db.relationship("KidsAiConsentEvent", back_populates="child")
    llm_calls = db.relationship("KidsAiLlmCall", back_populates="child")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class KidsAiConsentEvent(db.Model):
    """COPPA create-child log. Not deleted with conversations."""

    __tablename__ = "kids_ai_consent_event"

    id = db.Column(db.Integer, primary_key=True)
    parent_user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    child_id = db.Column(
        db.Integer, db.ForeignKey("kids_ai_child.id"), nullable=False, index=True
    )
    username = db.Column(db.String(20), nullable=False)
    display_name = db.Column(db.String(50), nullable=False)
    age_tier = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    parent = db.relationship("User", foreign_keys=[parent_user_id])
    child = db.relationship("KidsAiChild", back_populates="consent_events")


class KidsAiConversation(db.Model):
    __tablename__ = "kids_ai_conversation"

    TITLE_MODEL = "model"
    TITLE_TRUNCATED = "truncated"

    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(
        db.Integer,
        db.ForeignKey("kids_ai_child.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(db.String(120), nullable=True)
    title_source = db.Column(db.String(20), nullable=True)
    locked = db.Column(db.Boolean, nullable=False, default=False)
    running_summary = db.Column(db.Text, nullable=True)
    last_flag_concern = db.Column(db.Text, nullable=True)
    pass2_pending = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    modified_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    child = db.relationship("KidsAiChild", back_populates="conversations")
    messages = db.relationship(
        "KidsAiMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="KidsAiMessage.created_at",
    )
    moderation_results = db.relationship(
        "KidsAiModerationResult",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.Index("ix_kids_ai_conversation_child_modified", "child_id", "modified_at"),
        db.Index("ix_kids_ai_conversation_child_locked", "child_id", "locked"),
    )


class KidsAiMessage(db.Model):
    __tablename__ = "kids_ai_message"

    ROLE_CHILD = "child"
    ROLE_ASSISTANT = "assistant"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("kids_ai_conversation.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = db.Column(db.String(20), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    conversation = db.relationship("KidsAiConversation", back_populates="messages")

    __table_args__ = (
        db.Index("ix_kids_ai_message_conversation_created", "conversation_id", "created_at"),
    )


class KidsAiModerationResult(db.Model):
    """Flag / concern / summary only — not chat text."""

    __tablename__ = "kids_ai_moderation_result"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("kids_ai_conversation.id", ondelete="CASCADE"),
        nullable=False,
    )
    child_message_id = db.Column(
        db.Integer, db.ForeignKey("kids_ai_message.id"), nullable=False, index=True
    )
    assistant_message_id = db.Column(
        db.Integer, db.ForeignKey("kids_ai_message.id"), nullable=True
    )
    pass_number = db.Column(db.Integer, nullable=False)
    model = db.Column(db.String(80), nullable=False)
    flagged = db.Column(db.Boolean, nullable=True)
    concern = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    conversation = db.relationship(
        "KidsAiConversation", back_populates="moderation_results"
    )
    child_message = db.relationship(
        "KidsAiMessage", foreign_keys=[child_message_id]
    )
    assistant_message = db.relationship(
        "KidsAiMessage", foreign_keys=[assistant_message_id]
    )

    __table_args__ = (
        db.Index(
            "ix_kids_ai_moderation_result_conversation_created",
            "conversation_id",
            "created_at",
        ),
    )


class KidsAiLlmCall(db.Model):
    """Admin cost ledger. No prompt or response text. Survives conversation delete."""

    __tablename__ = "kids_ai_llm_call"

    KIND_PASS1 = "pass1"
    KIND_PRIMARY = "primary"
    KIND_PASS2 = "pass2"
    KIND_TITLE = "title"

    id = db.Column(db.Integer, primary_key=True)
    parent_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    child_id = db.Column(
        db.Integer, db.ForeignKey("kids_ai_child.id"), nullable=False
    )
    conversation_id = db.Column(
        db.Integer,
        db.ForeignKey("kids_ai_conversation.id", ondelete="SET NULL"),
        nullable=True,
    )
    child_message_id = db.Column(
        db.Integer,
        db.ForeignKey("kids_ai_message.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind = db.Column(db.String(20), nullable=False)
    model = db.Column(db.String(80), nullable=False)
    input_tokens = db.Column(db.Integer, nullable=True)
    output_tokens = db.Column(db.Integer, nullable=True)
    input_cost_usd = db.Column(db.Numeric(12, 6), nullable=True)
    output_cost_usd = db.Column(db.Numeric(12, 6), nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    parent = db.relationship("User", foreign_keys=[parent_user_id])
    child = db.relationship("KidsAiChild", back_populates="llm_calls")

    __table_args__ = (
        db.Index("ix_kids_ai_llm_call_parent_created", "parent_user_id", "created_at"),
        db.Index("ix_kids_ai_llm_call_child_created", "child_id", "created_at"),
        db.Index("ix_kids_ai_llm_call_child_message", "child_message_id"),
        db.Index("ix_kids_ai_llm_call_kind_created", "kind", "created_at"),
    )
