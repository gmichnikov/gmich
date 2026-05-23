"""SS to Cal — activity logging (LogEntry + PostHog)."""

import os

from posthog import Posthog

from app import db
from app.models import LogEntry

_posthog = Posthog(os.environ.get("POSTHOG_API_KEY", ""), host="https://us.i.posthog.com", sync_mode=True)


def log_share_not_logged_in() -> None:
    db.session.add(
        LogEntry(
            project="ss_to_cal",
            category="Share",
            actor_id=None,
            description="Share POST → outcome=not_logged_in",
        )
    )
    db.session.commit()


def log_share_extraction(
    *,
    actor_id: int,
    outcome: str,
    latency_ms: int,
    model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    confidence: str | None = None,
    fields_populated: int = 0,
    image_width: int | None = None,
    image_height: int | None = None,
    error_code: str | None = None,
    api_latency_ms: int | None = None,
) -> None:
    parts = [f"Extraction → outcome={outcome}", f"latency_ms={latency_ms}"]
    if model:
        parts.append(f"model={model}")
    if input_tokens or output_tokens:
        parts.append(f"input_tokens={input_tokens}")
        parts.append(f"output_tokens={output_tokens}")
    if api_latency_ms is not None:
        parts.append(f"api_latency_ms={api_latency_ms}")
    if confidence:
        parts.append(f"confidence={confidence}")
    if fields_populated:
        parts.append(f"fields_populated={fields_populated}")
    if image_width and image_height:
        parts.append(f"image={image_width}x{image_height}")
    if error_code:
        parts.append(f"error_code={error_code}")

    db.session.add(
        LogEntry(
            project="ss_to_cal",
            category="Extraction",
            actor_id=actor_id,
            description=". ".join(parts),
        )
    )
    db.session.commit()

    if os.environ.get("POSTHOG_API_KEY"):
        properties = {
            "project": "ss_to_cal",
            "outcome": outcome,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "fields_populated": fields_populated,
        }
        if model:
            properties["model"] = model
        if confidence:
            properties["confidence"] = confidence
        if image_width is not None:
            properties["image_width"] = image_width
        if image_height is not None:
            properties["image_height"] = image_height
        if error_code:
            properties["error_code"] = error_code
        if api_latency_ms is not None:
            properties["api_latency_ms"] = api_latency_ms

        _posthog.capture(
            "ss_to_cal_extraction",
            distinct_id=str(actor_id),
            properties=properties,
        )
