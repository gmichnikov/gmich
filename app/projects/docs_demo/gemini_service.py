"""
Docs Demo — Gemini API service.
Thin wrapper to call Gemini for text generation and comment generation.
"""

import json
import logging
import os
import re

from google import genai

MODEL = "gemini-3-flash-preview"
MAX_OUTPUT_TOKENS = 4096

logger = logging.getLogger(__name__)


def _get_client():
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable is not set")
    return genai.Client(api_key=api_key)


def generate_text(prompt: str, text: str) -> str:
    """
    Call Gemini with prompt + text, return plain text result.
    Used for /improve, /expand, /summarize, /brainstorm, and freeform prompts.
    """
    full_prompt = f"{prompt}\n\n{text}" if text else prompt
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=full_prompt,
        config={"max_output_tokens": MAX_OUTPUT_TOKENS},
    )
    result = (response.text or "").strip()
    logger.info("generate_text result (%d chars): %s", len(result), repr(result[:200]) + ("..." if len(result) > 200 else ""))
    return result


def generate_comments(prompt: str, document_text: str) -> list[dict]:
    """
    Call Gemini with prompt + document, parse JSON response as [{target, comment}, ...].
    Prompt must instruct Gemini to quote target text exactly from the document.
    Returns list of dicts with 'target' and 'comment' keys.
    """
    full_prompt = f"{prompt}\n\nDocument:\n{document_text}" if document_text else prompt
    client = _get_client()
    response = client.models.generate_content(
        model=MODEL,
        contents=full_prompt,
        config={"max_output_tokens": MAX_OUTPUT_TOKENS},
    )
    raw = (response.text or "").strip()

    # Gemini may wrap JSON in markdown code blocks
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        raw = match.group(1).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse Gemini comments JSON: %s", e)
        raise ValueError("Invalid JSON response from AI") from e

    if not isinstance(data, list):
        raise ValueError("Expected a JSON array")

    result = []
    for item in data:
        if isinstance(item, dict) and "target" in item and "comment" in item:
            result.append({"target": str(item["target"]), "comment": str(item["comment"])})
    return result
