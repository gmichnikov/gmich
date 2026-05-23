"""PRD §06 error codes, user-facing copy, and recovery actions."""

from __future__ import annotations

from typing import Literal, TypedDict

RecoveryAction = Literal["reshare", "go_back", "login"] | None
ErrorLevel = Literal["error", "info"]


class ErrorDisplay(TypedDict):
    message: str
    recovery: RecoveryAction
    level: ErrorLevel


ERROR_DISPLAY: dict[str, ErrorDisplay] = {
    "OFFLINE": {
        "message": "You're offline. Connect to the internet and try again.",
        "recovery": "reshare",
        "level": "error",
    },
    "NOT_LOGGED_IN": {
        "message": "Please log in, then share the screenshot again.",
        "recovery": "login",
        "level": "error",
    },
    "API_ERROR": {
        "message": "Couldn't reach the extraction service. Try again.",
        "recovery": "reshare",
        "level": "error",
    },
    "PARSE_FAILED": {
        "message": "The AI returned an unexpected response. Try again.",
        "recovery": "reshare",
        "level": "error",
    },
    "NO_EVENT_FOUND": {
        "message": "No event details were found in this image. You can fill in the details manually.",
        "recovery": None,
        "level": "info",
    },
    "IMAGE_TOO_LARGE": {
        "message": "The image couldn't be processed. Try a clearer screenshot.",
        "recovery": "go_back",
        "level": "error",
    },
    "IMAGE_MISSING": {
        "message": "No image was shared. Try sharing a screenshot again.",
        "recovery": "reshare",
        "level": "error",
    },
}


def error_display(error_code: str | None) -> ErrorDisplay | None:
    if not error_code:
        return None
    return ERROR_DISPLAY.get(error_code)
