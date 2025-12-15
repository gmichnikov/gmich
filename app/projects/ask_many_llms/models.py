"""
Ask Many LLMs Models
Database models for the Ask Many LLMs project
"""

from datetime import datetime
from app import db


class LLMQuestion(db.Model):
    """Ask Many LLMs: Question asked to multiple LLMs"""

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    credits_used = db.Column(db.Integer, nullable=False, default=1)
    summary_response_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "llm_response.id", use_alter=True, name="fk_question_summary_response"
        ),
        nullable=True,
    )

    user = db.relationship("User", backref=db.backref("llm_questions", lazy=True))
    responses = db.relationship(
        "LLMResponse",
        backref=db.backref("llm_question", lazy=True),
        foreign_keys="LLMResponse.question_id",
        cascade="all, delete-orphan",
    )
    summary_response = db.relationship(
        "LLMResponse", foreign_keys=[summary_response_id], uselist=False
    )

    def __repr__(self):
        return f"<LLMQuestion {self.id}: {self.content[:50]}...>"


class LLMResponse(db.Model):
    """Ask Many LLMs: Response from a specific LLM"""

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(
        db.Integer, db.ForeignKey("llm_question.id"), nullable=False
    )
    llm_name = db.Column(
        db.String(50), nullable=False
    )  # e.g., 'GPT-5 Mini', 'Claude Haiku 4.5', 'Gemini 2.5 Flash'
    model_name = db.Column(
        db.String(100), nullable=False
    )  # e.g., 'gpt-5-mini', 'claude-haiku-4-5', 'gemini-2.5-flash'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    input_tokens = db.Column(db.Integer, nullable=True)
    output_tokens = db.Column(db.Integer, nullable=True)
    total_tokens = db.Column(db.Integer, nullable=True)
    input_cost = db.Column(db.Float, nullable=True)
    output_cost = db.Column(db.Float, nullable=True)
    response_time = db.Column(db.Float, nullable=True)  # Time in seconds

    def __repr__(self):
        return f"<LLMResponse from {self.llm_name} ({self.model_name}) for LLMQuestion {self.question_id}>"
