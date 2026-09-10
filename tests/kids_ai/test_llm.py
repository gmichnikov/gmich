"""Claude response parsing for Kids AI."""

import unittest
from types import SimpleNamespace

from app.projects.kids_ai.llm import _anthropic_output_text, _gemini_output_text


class AnthropicOutputTextTestCase(unittest.TestCase):
    def test_skips_leading_thinking_block(self):
        response = SimpleNamespace(
            content=[
                SimpleNamespace(type="thinking", thinking=""),
                SimpleNamespace(type="text", text="Hi there!"),
            ]
        )
        self.assertEqual(_anthropic_output_text(response), "Hi there!")


class GeminiOutputTextTestCase(unittest.TestCase):
    def test_falls_back_to_candidate_parts(self):
        response = SimpleNamespace(
            text=None,
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        parts=[SimpleNamespace(text='{"flagged": false}')]
                    )
                )
            ],
        )
        self.assertEqual(_gemini_output_text(response), '{"flagged": false}')
