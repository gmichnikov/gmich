"""SS to Cal extraction unit tests."""

import pytest

from app.projects.ss_to_cal.extraction import (
    normalize_extraction,
    parse_json_from_llm,
)


def test_parse_json_from_llm_plain_object():
    parsed = parse_json_from_llm('{"title": "Meetup", "date": "2026-06-01"}')
    assert parsed["title"] == "Meetup"
    assert parsed["date"] == "2026-06-01"


def test_parse_json_from_llm_strips_markdown_fence():
    raw = '```json\n{"title": "Party", "confidence": "high"}\n```'
    parsed = parse_json_from_llm(raw)
    assert parsed["title"] == "Party"
    assert parsed["confidence"] == "high"


def test_normalize_extraction_time_aliases_and_formats():
    parsed = {
        "title": "Party",
        "date": "2026-06-01",
        "start_time": "7:30 PM",
        "endTime": "21:00:00",
    }
    result = normalize_extraction(parsed)
    assert result["startTime"] == "19:30"
    assert result["endTime"] == "21:00"
