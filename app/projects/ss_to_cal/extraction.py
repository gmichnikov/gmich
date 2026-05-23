"""Vision-model extraction for SS to Cal."""

import base64
import json
import logging
import os
import re
import signal
import time
from contextlib import contextmanager
from datetime import date

from google.genai import types
from posthog import Posthog
from posthog.ai.anthropic import Anthropic as PostHogAnthropicClient
from posthog.ai.gemini import Client as PostHogGeminiClient

logger = logging.getLogger(__name__)

_posthog = Posthog(os.environ.get("POSTHOG_API_KEY", ""), host="https://us.i.posthog.com", sync_mode=True)

DEFAULT_MODEL = os.getenv("SSTC_EXTRACTION_MODEL", "claude-sonnet-4-6")
MAX_OUTPUT_TOKENS = 1024
TIMEOUT_SECONDS = 45

SYSTEM_PROMPT = """You are an event extraction assistant. Your job is to extract
calendar event details from screenshots.

Rules you must follow without exception:
- Respond ONLY with a single valid JSON object. No explanation,
  no preamble, no markdown, no code fences.
- If you are not confident about a value, return null for that field.
- NEVER guess, infer, or fabricate dates, times, or locations.
- A null field is always preferable to a wrong field.
- If the image contains no identifiable event, return:
  {"error": "no_event_found"}
- Dates must be ISO 8601: YYYY-MM-DD
- Times must be 24-hour HH:MM format
- Timezone must be an IANA timezone name, e.g. "America/New_York"
- Use today's date (provided in the user message) to resolve relative phrases like "next Friday"."""

EXTRACTION_KEYS = (
    "title",
    "date",
    "startTime",
    "endTime",
    "location",
    "description",
    "timezone",
    "confidence",
)


class ExtractionApiError(Exception):
    """Vision API call failed."""


class ExtractionParseError(Exception):
    """Model response could not be parsed as JSON."""


@contextmanager
def _timeout_context(seconds: int):
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
        yield


def _user_message() -> str:
    return (
        f"Extract event details from this screenshot. "
        f"Today's date is {date.today().isoformat()} for resolving relative dates."
    )


def extract_event_from_image(jpeg_bytes: bytes, *, distinct_id: str) -> tuple[dict, dict]:
    """
    Call vision model on JPEG bytes.
    Returns (parsed_dict, metadata) with token counts and api_latency_ms.
    """
    model = DEFAULT_MODEL
    if model.startswith("claude"):
        return _extract_with_claude(jpeg_bytes, distinct_id=distinct_id, model=model)
    if model.startswith("gemini"):
        return _extract_with_gemini(jpeg_bytes, distinct_id=distinct_id, model=model)
    raise ExtractionApiError(f"Unsupported SSTC_EXTRACTION_MODEL: {model}")


def _extract_with_claude(jpeg_bytes: bytes, *, distinct_id: str, model: str) -> tuple[dict, dict]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ExtractionApiError("ANTHROPIC_API_KEY environment variable is not set")

    client = PostHogAnthropicClient(api_key=api_key, posthog_client=_posthog)
    api_started = time.monotonic()
    image_b64 = base64.standard_b64encode(jpeg_bytes).decode("ascii")

    with _timeout_context(TIMEOUT_SECONDS):
        response = client.messages.create(
            model=model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": _user_message()},
                    ],
                }
            ],
            posthog_distinct_id=distinct_id,
            posthog_properties={"project": "ss_to_cal"},
        )

    api_latency_ms = int((time.monotonic() - api_started) * 1000)
    text = _anthropic_text(response)
    if not text:
        raise ExtractionApiError("Vision model returned an empty response")

    parsed = parse_json_from_llm(text)
    metadata = {
        "model": model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "api_latency_ms": api_latency_ms,
    }
    return parsed, metadata


def _extract_with_gemini(jpeg_bytes: bytes, *, distinct_id: str, model: str) -> tuple[dict, dict]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ExtractionApiError("GOOGLE_API_KEY environment variable is not set")

    client = PostHogGeminiClient(api_key=api_key, posthog_client=_posthog)
    api_started = time.monotonic()

    with _timeout_context(TIMEOUT_SECONDS):
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                        types.Part.from_text(text=_user_message()),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
            posthog_distinct_id=distinct_id,
            posthog_properties={"project": "ss_to_cal"},
        )

    api_latency_ms = int((time.monotonic() - api_started) * 1000)
    text = (response.text or "").strip()
    if not text:
        raise ExtractionApiError("Vision model returned an empty response")

    parsed = parse_json_from_llm(text)
    usage = response.usage_metadata
    metadata = {
        "model": model,
        "input_tokens": (usage.prompt_token_count or 0) if usage else 0,
        "output_tokens": (usage.candidates_token_count or 0) if usage else 0,
        "api_latency_ms": api_latency_ms,
    }
    return parsed, metadata


def _anthropic_text(response) -> str:
    parts = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def parse_json_from_llm(raw: str) -> dict:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()

    start = text.find("{")
    if start == -1:
        logger.error("SS to Cal extraction: no JSON object in model response")
        raise ExtractionParseError("No JSON object found in model response")

    decoder = json.JSONDecoder()
    try:
        result, _end = decoder.raw_decode(text, start)
    except json.JSONDecodeError as exc:
        logger.error("SS to Cal extraction: invalid JSON: %s", exc)
        raise ExtractionParseError("Invalid JSON in model response") from exc

    if not isinstance(result, dict):
        raise ExtractionParseError("Model response was not a JSON object")

    return result


def normalize_extraction(parsed: dict | None) -> dict:
    """Map model output to form field dict; unknown keys dropped."""
    empty = {key: None for key in EXTRACTION_KEYS}
    if not parsed:
        return empty

    if parsed.get("error") == "no_event_found":
        return empty

    for key in EXTRACTION_KEYS:
        value = parsed.get(key)
        if value is None:
            continue
        if key == "confidence":
            if value in ("high", "medium", "low"):
                empty[key] = value
            continue
        if isinstance(value, str):
            value = value.strip()
            empty[key] = value or None
        else:
            empty[key] = value

    return empty


def is_no_event_found(parsed: dict) -> bool:
    return parsed.get("error") == "no_event_found"


def count_fields_populated(extraction: dict) -> int:
    field_keys = ("title", "date", "startTime", "endTime", "location", "description", "timezone")
    return sum(1 for key in field_keys if extraction.get(key))
