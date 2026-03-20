"""
MCP tool implementations for the personal bio server.

Tools: get_personal, get_work
"""

import json
import os

# Load data from JSON file (path relative to this module)
_DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")


def _load_data():
    """Load personal data from data.json."""
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_personal() -> dict:
    """Return personal and family life info: bio, contact, interests, family."""
    data = _load_data()
    return data.get("personal", {})


def get_work() -> dict:
    """Return work background: skills, projects, experience."""
    data = _load_data()
    return data.get("work", {})


# Tool definitions for MCP protocol (name -> handler)
TOOL_HANDLERS = {
    "get_personal": get_personal,
    "get_work": get_work,
}
