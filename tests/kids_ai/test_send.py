"""Pass 1 outage must not 500 when dropping an uncommitted child turn."""

import os
import unittest
from unittest.mock import patch

from flask import Flask

from app import db
from app.models import User
from app.projects.kids_ai.chat import send_child_message
from app.projects.kids_ai.llm import LlmResult
from app.projects.kids_ai.models import (
    KidsAiChild,
    KidsAiConversation,
    KidsAiLlmCall,
    KidsAiMessage,
    KidsAiParent,
)
from app.projects.kids_ai.pricing import MODEL_MODERATION_A, MODEL_MODERATION_B

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _create_test_app():
    app = Flask(__name__, template_folder=os.path.join(ROOT, "app", "templates"))
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = "test-secret"
    db.init_app(app)
    return app


class Pass1OutageTestCase(unittest.TestCase):
    def setUp(self):
        self.app = _create_test_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        parent = User(
            email="parent@example.com",
            full_name="Parent",
            short_name="P",
            time_zone="UTC",
            credits=5,
            email_verified=True,
        )
        parent.set_password("secret")
        db.session.add(parent)
        db.session.flush()
        db.session.add(KidsAiParent(user_id=parent.id))
        child = KidsAiChild(
            parent_user_id=parent.id,
            username="testkid",
            display_name="Kid",
            age_tier=KidsAiChild.AGE_TWEEN,
        )
        child.set_password("pass")
        db.session.add(child)
        db.session.commit()
        self.child_id = child.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_pass1_outage_does_not_save_turn(self):
        child = KidsAiChild.query.get(self.child_id)
        gemini_ok = LlmResult(
            model=MODEL_MODERATION_A,
            text='{"flagged": false, "concern": null}',
        )
        openai_fail = LlmResult(
            model=MODEL_MODERATION_B,
            error="Unsupported value: reasoning_effort 'minimal'",
        )
        with patch(
            "app.projects.kids_ai.chat.run_moderation_pair",
            return_value=(gemini_ok, openai_fail),
        ):
            outcome = send_child_message(child, "hello")

        self.assertEqual(outcome.status, "retry")
        self.assertEqual(outcome.code, "pass1_outage")
        self.assertEqual(outcome.http_status, 503)
        self.assertEqual(KidsAiMessage.query.count(), 0)
        self.assertEqual(KidsAiConversation.query.count(), 0)
        self.assertEqual(KidsAiLlmCall.query.count(), 2)
        self.assertTrue(all(call.child_message_id is None for call in KidsAiLlmCall.query))
