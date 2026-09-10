"""Child send path: Pass 1 → credit → Claude → title → Pass 2."""

import json
import logging
from datetime import datetime

from app import db
from app.models import LogEntry, User
from app.projects.kids_ai.emails import send_flag_email
from app.projects.kids_ai.llm import (
    call_primary,
    call_title,
    run_moderation_pair,
    usage_costs,
)
from app.projects.kids_ai.models import (
    KidsAiConversation,
    KidsAiLlmCall,
    KidsAiMessage,
    KidsAiModerationResult,
)
from app.projects.kids_ai.prompts import (
    pass1_prompt,
    pass2_prompt,
    system_prompt_for,
    title_prompt,
)
from app.projects.kids_ai.render import render_assistant_html

logger = logging.getLogger(__name__)

CHILD_MESSAGE_MAX = 2000
MODERATION_WINDOW = 20
TITLE_MAX_CHARS = 60
PASS2_STALE_SECONDS = 90

LOCK_WARNING = (
    "This conversation had to stop. A parent will take a look. You can start a new one."
)
PAUSE_WARNING = "Chatting is paused until a parent allows it again."
NO_CREDITS_WARNING = "Can't send right now. Please try again later."
RETRY_WARNING = "Something went wrong. Please try again."
CLAUDE_FAIL_WARNING = "Couldn't get a reply. Please try again."


class ChatOutcome:
    def __init__(
        self,
        status,
        code,
        http_status=200,
        conversation=None,
        child_message=None,
        assistant_message=None,
        warning=None,
    ):
        self.status = status
        self.code = code
        self.http_status = http_status
        self.conversation = conversation
        self.child_message = child_message
        self.assistant_message = assistant_message
        self.warning = warning


def age_tier_label(age_tier):
    from app.projects.kids_ai.prompts import AGE_TIER_LABELS

    return AGE_TIER_LABELS.get(age_tier, age_tier)


def truncated_title(text):
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= TITLE_MAX_CHARS:
        return cleaned or "Conversation"
    return cleaned[: TITLE_MAX_CHARS - 3].rstrip() + "..."


def can_child_send(child, parent=None):
    if child.paused:
        return False, "paused"
    parent = parent or User.query.get(child.parent_user_id)
    if parent is None or (parent.credits or 0) < 1:
        return False, "no_credits"
    return True, None


def format_line(message):
    who = "child" if message.role == KidsAiMessage.ROLE_CHILD else "assistant"
    return f"[{who}] {message.body}"


def conversation_messages(conversation):
    return (
        KidsAiMessage.query.filter_by(conversation_id=conversation.id)
        .order_by(KidsAiMessage.created_at, KidsAiMessage.id)
        .all()
    )


def recent_message_lines(messages, exclude_ids=None, limit=MODERATION_WINDOW):
    exclude_ids = set(exclude_ids or [])
    kept = [m for m in messages if m.id not in exclude_ids]
    return [format_line(m) for m in kept[-limit:]]


def parse_moderation_json(text, require_summary=False):
    if not text:
        raise ValueError("empty moderation response")
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(
            lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        ).strip()
    start = raw.find("{")
    if start == -1:
        raise ValueError("no JSON object")
    obj, _end = json.JSONDecoder().raw_decode(raw, start)
    if not isinstance(obj, dict):
        raise ValueError("JSON is not an object")
    flagged = obj.get("flagged")
    if flagged in ("true", "True", 1, "1"):
        flagged = True
    elif flagged in ("false", "False", 0, "0"):
        flagged = False
    if flagged is not True and flagged is not False:
        raise ValueError("flagged missing")
    concern = obj.get("concern")
    if concern is not None:
        concern = str(concern).strip() or None
    summary = obj.get("summary")
    if summary is not None:
        summary = str(summary).strip() or None
    if require_summary and not summary:
        raise ValueError("summary missing")
    return flagged, concern, summary


def record_llm_call(
    *,
    parent_user_id,
    child_id,
    conversation_id,
    child_message_id,
    kind,
    result,
):
    in_cost, out_cost = usage_costs(
        result.model, result.input_tokens, result.output_tokens
    )
    db.session.add(
        KidsAiLlmCall(
            parent_user_id=parent_user_id,
            child_id=child_id,
            conversation_id=conversation_id,
            child_message_id=child_message_id,
            kind=kind,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            input_cost_usd=in_cost,
            output_cost_usd=out_cost,
            error=result.error,
        )
    )


def record_moderation(
    *,
    conversation,
    child_message,
    assistant_message,
    pass_number,
    result,
    flagged,
    concern,
    summary,
    parse_error,
):
    db.session.add(
        KidsAiModerationResult(
            conversation_id=conversation.id,
            child_message_id=child_message.id,
            assistant_message_id=assistant_message.id if assistant_message else None,
            pass_number=pass_number,
            model=result.model,
            flagged=flagged,
            concern=concern,
            summary=summary,
            error=result.error or parse_error,
        )
    )


def apply_lock(conversation, child, parent, concern):
    conversation.locked = True
    conversation.last_flag_concern = concern
    conversation.pass2_pending = False
    conversation.modified_at = datetime.utcnow()
    child.lock_count = (child.lock_count or 0) + 1
    if child.lock_count >= 3:
        child.paused = True
    db.session.add(
        LogEntry(
            project="kids_ai",
            category="Lock Conversation",
            actor_id=parent.id,
            description=(
                f"Locked conversation {conversation.id} for child {child.username} "
                f"(lock_count={child.lock_count}, paused={child.paused})"
            ),
        )
    )
    db.session.flush()


def _choose_summary(parsed_rows):
    """parsed_rows: list of (flagged, concern, summary). Prefer an unflagged summary."""
    unflagged = [s for flagged, _c, s in parsed_rows if flagged is False and s]
    if unflagged:
        return unflagged[0]
    flagged = [s for flagged, _c, s in parsed_rows if flagged is True and s]
    if flagged:
        return flagged[0]
    any_summary = [s for _f, _c, s in parsed_rows if s]
    return any_summary[0] if any_summary else None


def _choose_concern(parsed_rows):
    for flagged, concern, _s in parsed_rows:
        if flagged and concern:
            return concern
    return "Something in this conversation looked concerning."


def _evaluate_pass(results, require_summary=False):
    """Return (decision, parsed_list).

    decision is 'flag', 'clear', or 'error'.
    parsed_list items are (result, flagged, concern, summary, parse_error).
    """
    parsed = []
    any_flag = False
    any_error = False
    for result in results:
        flagged = None
        concern = None
        summary = None
        parse_error = None
        if result.error or not result.ok:
            any_error = True
            parse_error = result.error or "empty response"
        else:
            try:
                flagged, concern, summary = parse_moderation_json(
                    result.text, require_summary=require_summary
                )
                if flagged:
                    any_flag = True
            except (ValueError, json.JSONDecodeError) as exc:
                any_error = True
                parse_error = str(exc)[:300]
        parsed.append((result, flagged, concern, summary, parse_error))

    if any_flag:
        return "flag", parsed
    if any_error:
        return "error", parsed
    return "clear", parsed


def _maybe_set_title(conversation, child, parent, child_message, assistant_message):
    if conversation.title:
        return
    first_child = next(
        (
            m
            for m in conversation_messages(conversation)
            if m.role == KidsAiMessage.ROLE_CHILD
        ),
        child_message,
    )
    result = call_title(title_prompt(first_child.body, assistant_message.body))
    record_llm_call(
        parent_user_id=parent.id,
        child_id=child.id,
        conversation_id=conversation.id,
        child_message_id=child_message.id,
        kind=KidsAiLlmCall.KIND_TITLE,
        result=result,
    )
    if result.ok:
        title = " ".join(result.text.split()).strip(" \"'")
        if title:
            conversation.title = title[:120]
            conversation.title_source = KidsAiConversation.TITLE_MODEL
            return
    conversation.title = truncated_title(first_child.body)
    conversation.title_source = KidsAiConversation.TITLE_TRUNCATED


def _set_truncated_title_if_needed(conversation, child_message):
    if conversation.title:
        return
    conversation.title = truncated_title(child_message.body)
    conversation.title_source = KidsAiConversation.TITLE_TRUNCATED


def message_payload(message):
    data = {
        "id": message.id,
        "role": message.role,
        "body": message.body,
        "created_at": message.created_at.isoformat() + "Z",
    }
    if message.role == KidsAiMessage.ROLE_ASSISTANT:
        data["body_html"] = render_assistant_html(message.body)
    return data


def outcome_payload(outcome):
    conversation = outcome.conversation
    return {
        "status": outcome.status,
        "code": outcome.code,
        "warning": outcome.warning,
        "conversation_id": conversation.id if conversation else None,
        "title": conversation.title if conversation else None,
        "locked": bool(conversation.locked) if conversation else False,
        "pass2_pending": bool(conversation.pass2_pending) if conversation else False,
        "paused": bool(getattr(conversation, "child", None) and conversation.child.paused)
        if conversation
        else False,
        "child_message": (
            message_payload(outcome.child_message) if outcome.child_message else None
        ),
        "assistant_message": (
            message_payload(outcome.assistant_message)
            if outcome.assistant_message
            else None
        ),
    }


def send_child_message(child, body, conversation_id=None):
    parent = User.query.get(child.parent_user_id)
    allowed, reason = can_child_send(child, parent)
    if not allowed:
        warning = PAUSE_WARNING if reason == "paused" else NO_CREDITS_WARNING
        return ChatOutcome(
            "blocked", reason, http_status=400, warning=warning
        )

    text = (body or "").strip()
    if not text:
        return ChatOutcome("blocked", "empty", http_status=400, warning="Type a message first.")
    if len(text) > CHILD_MESSAGE_MAX:
        return ChatOutcome(
            "blocked",
            "too_long",
            http_status=400,
            warning=f"Messages can be at most {CHILD_MESSAGE_MAX} characters.",
        )

    created_new = False
    if conversation_id:
        conversation = KidsAiConversation.query.filter_by(
            id=conversation_id, child_id=child.id
        ).first()
        if conversation is None:
            return ChatOutcome("blocked", "not_found", http_status=404, warning="Conversation not found.")
        if conversation.locked:
            return ChatOutcome(
                "blocked",
                "locked",
                http_status=403,
                conversation=conversation,
                warning=LOCK_WARNING,
            )
        if conversation.pass2_pending:
            return ChatOutcome(
                "blocked",
                "pass2_pending",
                http_status=409,
                conversation=conversation,
                warning="Please wait a moment.",
            )
    else:
        conversation = KidsAiConversation(child_id=child.id)
        db.session.add(conversation)
        db.session.flush()
        created_new = True

    child_message = KidsAiMessage(
        conversation_id=conversation.id,
        role=KidsAiMessage.ROLE_CHILD,
        body=text,
    )
    db.session.add(child_message)
    conversation.modified_at = datetime.utcnow()
    db.session.flush()

    messages = conversation_messages(conversation)
    recent = recent_message_lines(messages, exclude_ids={child_message.id})
    prompt = pass1_prompt(
        child.age_tier, conversation.running_summary, recent, text
    )
    result_a, result_b = run_moderation_pair(prompt)
    decision, parsed = _evaluate_pass([result_a, result_b], require_summary=False)

    for result, flagged, concern, summary, parse_error in parsed:
        record_llm_call(
            parent_user_id=parent.id,
            child_id=child.id,
            conversation_id=conversation.id,
            child_message_id=child_message.id,
            kind=KidsAiLlmCall.KIND_PASS1,
            result=result,
        )
        record_moderation(
            conversation=conversation,
            child_message=child_message,
            assistant_message=None,
            pass_number=1,
            result=result,
            flagged=flagged,
            concern=concern,
            summary=summary,
            parse_error=parse_error,
        )

    if decision == "error":
        db.session.delete(child_message)
        if created_new:
            db.session.delete(conversation)
        db.session.commit()
        return ChatOutcome("retry", "pass1_outage", http_status=503, warning=RETRY_WARNING)

    if decision == "flag":
        concern = _choose_concern(
            [(flagged, concern, summary) for _r, flagged, concern, summary, _e in parsed]
        )
        _set_truncated_title_if_needed(conversation, child_message)
        apply_lock(conversation, child, parent, concern)
        db.session.commit()
        send_flag_email(parent, child, conversation, concern, child.paused)
        warning = PAUSE_WARNING if child.paused else LOCK_WARNING
        return ChatOutcome(
            "locked",
            "flagged",
            conversation=conversation,
            child_message=child_message,
            warning=warning,
        )

    parent.credits = (parent.credits or 0) - 1
    db.session.add(
        LogEntry(
            project="kids_ai",
            category="Credit Usage",
            actor_id=parent.id,
            description=(
                f"Used 1 credit for Kids AI child {child.username} "
                f"conversation {conversation.id}. Remaining: {parent.credits}"
            ),
        )
    )
    db.session.flush()

    history = []
    for message in conversation_messages(conversation):
        role = "user" if message.role == KidsAiMessage.ROLE_CHILD else "assistant"
        history.append({"role": role, "content": message.body})

    primary = call_primary(system_prompt_for(child.age_tier), history)
    record_llm_call(
        parent_user_id=parent.id,
        child_id=child.id,
        conversation_id=conversation.id,
        child_message_id=child_message.id,
        kind=KidsAiLlmCall.KIND_PRIMARY,
        result=primary,
    )

    if not primary.ok:
        db.session.commit()
        return ChatOutcome(
            "retry",
            "claude_failed",
            http_status=502,
            conversation=conversation,
            child_message=child_message,
            warning=CLAUDE_FAIL_WARNING,
        )

    assistant_message = KidsAiMessage(
        conversation_id=conversation.id,
        role=KidsAiMessage.ROLE_ASSISTANT,
        body=primary.text,
    )
    db.session.add(assistant_message)
    conversation.pass2_pending = True
    conversation.modified_at = datetime.utcnow()
    _set_truncated_title_if_needed(conversation, child_message)
    db.session.flush()
    db.session.commit()

    return ChatOutcome(
        "ok",
        "replied",
        conversation=conversation,
        child_message=child_message,
        assistant_message=assistant_message,
    )


def finish_pass2(child, conversation_id):
    query = KidsAiConversation.query.filter_by(id=conversation_id, child_id=child.id)
    try:
        conversation = query.with_for_update().first()
    except Exception:
        conversation = query.first()
    if conversation is None:
        return ChatOutcome("blocked", "not_found", http_status=404, warning="Conversation not found.")
    if conversation.locked:
        warning = PAUSE_WARNING if child.paused else LOCK_WARNING
        return ChatOutcome(
            "locked",
            "already_locked",
            conversation=conversation,
            warning=warning,
        )
    if not conversation.pass2_pending:
        return ChatOutcome("ok", "already_clear", conversation=conversation)

    parent = User.query.get(child.parent_user_id)
    messages = conversation_messages(conversation)
    child_message = next(
        (m for m in reversed(messages) if m.role == KidsAiMessage.ROLE_CHILD),
        None,
    )
    assistant_message = next(
        (m for m in reversed(messages) if m.role == KidsAiMessage.ROLE_ASSISTANT),
        None,
    )
    if child_message is None or assistant_message is None:
        conversation.pass2_pending = False
        db.session.commit()
        return ChatOutcome("ok", "pass2_skipped", conversation=conversation)

    exclude = {child_message.id, assistant_message.id}
    recent = recent_message_lines(messages, exclude_ids=exclude)
    exchange = [format_line(child_message), format_line(assistant_message)]
    prompt = pass2_prompt(
        child.age_tier, conversation.running_summary, recent, exchange
    )
    result_a, result_b = run_moderation_pair(prompt)
    decision, parsed = _evaluate_pass([result_a, result_b], require_summary=False)

    for result, flagged, concern, summary, parse_error in parsed:
        record_llm_call(
            parent_user_id=parent.id,
            child_id=child.id,
            conversation_id=conversation.id,
            child_message_id=child_message.id,
            kind=KidsAiLlmCall.KIND_PASS2,
            result=result,
        )
        record_moderation(
            conversation=conversation,
            child_message=child_message,
            assistant_message=assistant_message,
            pass_number=2,
            result=result,
            flagged=flagged,
            concern=concern,
            summary=summary,
            parse_error=parse_error,
        )

    parsed_rows = [
        (flagged, concern, summary) for _r, flagged, concern, summary, _e in parsed
    ]
    summary = _choose_summary(parsed_rows)
    if summary:
        conversation.running_summary = summary

    assistant_count = sum(
        1 for m in messages if m.role == KidsAiMessage.ROLE_ASSISTANT
    )
    if assistant_count == 1 and conversation.title_source != KidsAiConversation.TITLE_MODEL:
        _maybe_set_title(conversation, child, parent, child_message, assistant_message)

    if decision == "error":
        logger.warning(
            "Kids AI Pass 2 outage on conversation %s; re-enabling send",
            conversation.id,
        )
        conversation.pass2_pending = False
        db.session.commit()
        return ChatOutcome("ok", "pass2_outage", conversation=conversation)

    if decision == "flag":
        concern = _choose_concern(parsed_rows)
        apply_lock(conversation, child, parent, concern)
        db.session.commit()
        send_flag_email(parent, child, conversation, concern, child.paused)
        warning = PAUSE_WARNING if child.paused else LOCK_WARNING
        return ChatOutcome(
            "locked",
            "flagged",
            conversation=conversation,
            child_message=child_message,
            assistant_message=assistant_message,
            warning=warning,
        )

    conversation.pass2_pending = False
    conversation.modified_at = datetime.utcnow()
    db.session.commit()
    return ChatOutcome(
        "ok",
        "clear",
        conversation=conversation,
        child_message=child_message,
        assistant_message=assistant_message,
    )


def conversation_status(child, conversation_id):
    conversation = KidsAiConversation.query.filter_by(
        id=conversation_id, child_id=child.id
    ).first()
    if conversation is None:
        return ChatOutcome("blocked", "not_found", http_status=404, warning="Conversation not found.")

    if (
        conversation.pass2_pending
        and conversation.modified_at
        and (datetime.utcnow() - conversation.modified_at).total_seconds()
        > PASS2_STALE_SECONDS
    ):
        logger.warning(
            "Kids AI Pass 2 stale on conversation %s; clearing pending",
            conversation.id,
        )
        conversation.pass2_pending = False
        db.session.commit()

    if conversation.locked:
        warning = PAUSE_WARNING if child.paused else LOCK_WARNING
        return ChatOutcome(
            "locked",
            "locked",
            conversation=conversation,
            warning=warning,
        )
    return ChatOutcome("ok", "ready", conversation=conversation)


def delete_conversation(conversation):
    KidsAiLlmCall.query.filter_by(conversation_id=conversation.id).update(
        {
            KidsAiLlmCall.conversation_id: None,
            KidsAiLlmCall.child_message_id: None,
        }
    )
    db.session.delete(conversation)
