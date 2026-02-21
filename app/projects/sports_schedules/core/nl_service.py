"""
Natural language to query LLM service for Sports Schedules.
Calls Gemini to translate natural language questions into query config JSON.
"""

import os
import signal
from contextlib import contextmanager

from google import genai

MODEL = "gemini-3-flash-preview"
MAX_OUTPUT_TOKENS = 2048
TIMEOUT_SECONDS = 60


def _timeout_context(seconds: int):
    """Context manager for timing out long-running operations (Unix-like systems)."""
    def _handler(signum, frame):
        raise TimeoutError(f"Operation timed out after {seconds} seconds")

    try:
        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    except (AttributeError, ValueError):
        # Systems without SIGALRM (e.g. Windows): no timeout
        yield


def call_nl_llm(prompt: str) -> tuple[str, dict]:
    """
    Call Gemini to translate natural language to query config.
    Returns (response_text, metadata_dict).
    metadata_dict has input_tokens, output_tokens (from usage_metadata when available).
    Raises on timeout or API errors.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")

    client = genai.Client(api_key=api_key)

    with _timeout_context(TIMEOUT_SECONDS):
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config={"max_output_tokens": MAX_OUTPUT_TOKENS},
        )

    text = response.text or ""
    usage = response.usage_metadata
    input_tokens = (usage.prompt_token_count or 0) if usage else 0
    output_tokens = (usage.candidates_token_count or 0) if usage else 0

    metadata = {
        "input_tokens": input_tokens or 0,
        "output_tokens": output_tokens or 0,
    }
    return (text, metadata)
