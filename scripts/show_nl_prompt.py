#!/usr/bin/env python
"""Print the full NL prompt for a given question. Run from project root with venv activated."""
import sys
sys.path.insert(0, '.')

# Import app first to set up Flask (needed for app.projects... imports)
from app import create_app
app = create_app()
with app.app_context():
    from app.projects.sports_schedules.core.nl_prompt import build_nl_prompt

    question = sys.argv[1] if len(sys.argv) > 1 else "When do the Celtics play OKC?"
    today = sys.argv[2] if len(sys.argv) > 2 else "2026-02-20"

    prompt = build_nl_prompt(question, today)
    print("=" * 60)
    print("FULL NL PROMPT")
    print(f"Question: {question}")
    print(f"Today: {today}")
    print("=" * 60)
    print(prompt)
    print("=" * 60)
    print(f"Length: {len(prompt)} chars")
