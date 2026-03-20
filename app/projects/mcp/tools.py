"""
MCP tool implementations for the personal bio server.

Tools: get_bio, get_skills, get_projects, get_experience, get_contact,
       get_resume, answer_question
"""

import json
import os

# Load data from JSON file (path relative to this module)
_DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")


def _load_data():
    """Load personal data from data.json."""
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_bio(short: bool = True) -> dict:
    """Return short or long biography."""
    data = _load_data()
    key = "short" if short else "long"
    return {"bio": data["bio"].get(key, "")}


def get_skills() -> dict:
    """Return technical and professional skills."""
    data = _load_data()
    return {"skills": data.get("skills", [])}


def get_projects() -> dict:
    """Return portfolio projects with links, stack, outcomes."""
    data = _load_data()
    return {"projects": data.get("projects", [])}


def get_experience() -> dict:
    """Return work history."""
    data = _load_data()
    return {"experience": data.get("experience", [])}


def get_contact() -> dict:
    """Return contact info and socials."""
    data = _load_data()
    return {"contact": data.get("contact", {})}


def get_resume() -> dict:
    """Return full structured résumé."""
    return _load_data()


def answer_question(question: str) -> dict:
    """
    Freeform Q&A about you, powered by Claude with your data as context.
    Stub for now — will need Claude API integration.
    """
    # TODO: Integrate with Claude API, pass data as context
    return {"answer": f"Question received: {question}. (answer_question not yet implemented)"}


# Tool definitions for MCP protocol (name -> handler)
TOOL_HANDLERS = {
    "get_bio": get_bio,
    "get_skills": get_skills,
    "get_projects": get_projects,
    "get_experience": get_experience,
    "get_contact": get_contact,
    "get_resume": get_resume,
    "answer_question": answer_question,
}
