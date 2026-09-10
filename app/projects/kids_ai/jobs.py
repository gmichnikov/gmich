"""Daily digest collection and 30-day conversation retention."""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from app import db
from app.models import LogEntry, User
from app.projects.kids_ai.chat import delete_conversation
from app.projects.kids_ai.emails import send_digest_email, snippet
from app.projects.kids_ai.models import KidsAiChild, KidsAiConversation, KidsAiParent

logger = logging.getLogger(__name__)

DIGEST_WINDOW_HOURS = 24
RETENTION_DAYS = 30


def _cutoff(hours=DIGEST_WINDOW_HOURS, now=None):
    now = now or datetime.utcnow()
    return now - timedelta(hours=hours)


def collect_digest_activity(hours=DIGEST_WINDOW_HOURS, now=None, parent_user_id=None):
    """Group conversations updated in the window by allowlisted parent, then child.

    Returns {parent_user_id: [(child, [conversation, ...]), ...]}.
    """
    cutoff = _cutoff(hours=hours, now=now)
    query = KidsAiConversation.query.filter(KidsAiConversation.modified_at >= cutoff)
    if parent_user_id is not None:
        query = query.join(KidsAiChild).filter(KidsAiChild.parent_user_id == parent_user_id)
    conversations = query.order_by(
        KidsAiConversation.modified_at.desc(), KidsAiConversation.id.desc()
    ).all()

    allowlisted = {
        row.user_id for row in KidsAiParent.query.with_entities(KidsAiParent.user_id)
    }
    grouped = defaultdict(lambda: defaultdict(list))
    children = {}
    for conversation in conversations:
        child = conversation.child
        if child is None or child.parent_user_id not in allowlisted:
            continue
        children[child.id] = child
        grouped[child.parent_user_id][child.id].append(conversation)

    result = {}
    for user_id, by_child in grouped.items():
        result[user_id] = [
            (children[child_id], convs) for child_id, convs in by_child.items()
        ]
        result[user_id].sort(key=lambda item: item[0].display_name.lower())
    return result


def digest_child_lines(child, conversations):
    """Plain-text lines for one child in the digest."""
    count = len(conversations)
    noun = "conversation" if count == 1 else "conversations"
    lines = [f"{child.display_name} — {count} {noun}"]
    for conversation in conversations:
        title = conversation.title or "Untitled conversation"
        locked = " (locked)" if conversation.locked else ""
        body = snippet(conversation.running_summary) or "No summary stored yet."
        lines.append(f"  • {title}{locked}: {body}")
    return lines


def run_daily_digest(hours=DIGEST_WINDOW_HOURS, parent_user_id=None, dry_run=False):
    """Send one digest per allowlisted parent with activity. No send log table."""
    activity = collect_digest_activity(hours=hours, parent_user_id=parent_user_id)
    sent = 0
    failed = 0
    skipped = 0

    if not activity:
        return {"sent": 0, "failed": 0, "skipped": 0, "parents": 0}

    for user_id, child_rows in activity.items():
        parent = User.query.get(user_id)
        if parent is None or not parent.email:
            skipped += 1
            logger.warning("Kids AI digest skipped: parent %s has no email", user_id)
            continue

        child_blocks = []
        for child, conversations in child_rows:
            child_blocks.append(
                {
                    "child": child,
                    "conversations": conversations,
                    "lines": digest_child_lines(child, conversations),
                }
            )

        if dry_run:
            sent += 1
            continue

        try:
            send_digest_email(parent, child_blocks)
            sent += 1
        except Exception:
            failed += 1
            logger.exception("Kids AI digest failed for %s", parent.email)

    if not dry_run and sent:
        db.session.add(
            LogEntry(
                project="kids_ai",
                category="Daily Digest",
                actor_id=None,
                description=f"Sent Kids AI digest to {sent} parent(s); failed={failed}",
            )
        )
        db.session.commit()

    return {
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "parents": len(activity),
    }


def run_retention(days=RETENTION_DAYS, dry_run=False):
    """Hard-delete conversations with modified_at older than ``days``."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    conversations = KidsAiConversation.query.filter(
        KidsAiConversation.modified_at < cutoff
    ).all()
    count = len(conversations)
    if dry_run or count == 0:
        return {"deleted": 0 if dry_run else count, "found": count, "dry_run": dry_run}

    for conversation in conversations:
        delete_conversation(conversation)

    db.session.add(
        LogEntry(
            project="kids_ai",
            category="Retention",
            actor_id=None,
            description=f"Deleted {count} Kids AI conversation(s) older than {days} days",
        )
    )
    db.session.commit()
    return {"deleted": count, "found": count, "dry_run": False}
