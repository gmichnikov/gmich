"""Tests for PRD §06 error display copy."""

from app.projects.ss_to_cal.error_states import ERROR_DISPLAY, error_display


def test_error_display_known_codes():
    for code in (
        "OFFLINE",
        "NOT_LOGGED_IN",
        "API_ERROR",
        "PARSE_FAILED",
        "NO_EVENT_FOUND",
        "IMAGE_TOO_LARGE",
    ):
        display = error_display(code)
        assert display is not None
        assert display["message"]
        assert display["level"] in ("error", "info")


def test_no_event_found_is_info_level():
    display = error_display("NO_EVENT_FOUND")
    assert display["level"] == "info"
    assert display["recovery"] is None


def test_api_error_has_reshare_recovery():
    display = error_display("API_ERROR")
    assert display["recovery"] == "reshare"


def test_image_too_large_has_go_back_recovery():
    display = error_display("IMAGE_TOO_LARGE")
    assert display["recovery"] == "go_back"


def test_unknown_code_returns_none():
    assert error_display("UNKNOWN") is None


def test_all_entries_have_messages():
    assert len(ERROR_DISPLAY) >= 7
