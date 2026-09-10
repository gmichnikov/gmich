"""Admin API-cost rollups. No prompt or chat text."""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func

from app import db
from app.models import User
from app.projects.kids_ai.models import KidsAiChild, KidsAiLlmCall

KIND_LABELS = {
    KidsAiLlmCall.KIND_PASS1: "Pass 1",
    KidsAiLlmCall.KIND_PRIMARY: "Primary",
    KidsAiLlmCall.KIND_PASS2: "Pass 2",
    KidsAiLlmCall.KIND_TITLE: "Title",
}

COST_DAY_CHOICES = (7, 30, 0)


def since_for_days(days):
    if not days:
        return None
    return datetime.utcnow() - timedelta(days=int(days))


def format_usd(value):
    if value is None:
        return "—"
    amount = Decimal(value)
    return f"${amount.quantize(Decimal('0.0001'))}"


def _cost_expr():
    return func.coalesce(KidsAiLlmCall.input_cost_usd, 0) + func.coalesce(
        KidsAiLlmCall.output_cost_usd, 0
    )


def summarize(since=None, parent_user_id=None, child_id=None):
    query = db.session.query(
        func.count(KidsAiLlmCall.id),
        func.coalesce(func.sum(KidsAiLlmCall.input_tokens), 0),
        func.coalesce(func.sum(KidsAiLlmCall.output_tokens), 0),
        func.coalesce(func.sum(_cost_expr()), 0),
        func.sum(case((KidsAiLlmCall.error.isnot(None), 1), else_=0)),
    )
    if since is not None:
        query = query.filter(KidsAiLlmCall.created_at >= since)
    if parent_user_id is not None:
        query = query.filter(KidsAiLlmCall.parent_user_id == parent_user_id)
    if child_id is not None:
        query = query.filter(KidsAiLlmCall.child_id == child_id)
    calls, input_tokens, output_tokens, usd, errors = query.one()
    return {
        "calls": int(calls or 0),
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "usd": usd or Decimal("0"),
        "errors": int(errors or 0),
    }


def totals_by_kind(since=None, parent_user_id=None, child_id=None):
    query = db.session.query(
        KidsAiLlmCall.kind,
        func.count(KidsAiLlmCall.id),
        func.coalesce(func.sum(KidsAiLlmCall.input_tokens), 0),
        func.coalesce(func.sum(KidsAiLlmCall.output_tokens), 0),
        func.coalesce(func.sum(_cost_expr()), 0),
    )
    if since is not None:
        query = query.filter(KidsAiLlmCall.created_at >= since)
    if parent_user_id is not None:
        query = query.filter(KidsAiLlmCall.parent_user_id == parent_user_id)
    if child_id is not None:
        query = query.filter(KidsAiLlmCall.child_id == child_id)
    rows = query.group_by(KidsAiLlmCall.kind).all()
    order = [
        KidsAiLlmCall.KIND_PASS1,
        KidsAiLlmCall.KIND_PRIMARY,
        KidsAiLlmCall.KIND_PASS2,
        KidsAiLlmCall.KIND_TITLE,
    ]
    by_kind = {
        kind: {
            "kind": kind,
            "label": KIND_LABELS.get(kind, kind),
            "calls": int(calls),
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "usd": usd or Decimal("0"),
        }
        for kind, calls, input_tokens, output_tokens, usd in rows
    }
    return [
        by_kind.get(
            kind,
            {
                "kind": kind,
                "label": KIND_LABELS.get(kind, kind),
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "usd": Decimal("0"),
            },
        )
        for kind in order
        if kind in by_kind
    ] or list(by_kind.values())


def totals_by_parent(since=None):
    query = db.session.query(
        KidsAiLlmCall.parent_user_id,
        func.count(KidsAiLlmCall.id),
        func.coalesce(func.sum(_cost_expr()), 0),
        func.coalesce(func.sum(KidsAiLlmCall.input_tokens), 0),
        func.coalesce(func.sum(KidsAiLlmCall.output_tokens), 0),
    )
    if since is not None:
        query = query.filter(KidsAiLlmCall.created_at >= since)
    rows = (
        query.group_by(KidsAiLlmCall.parent_user_id)
        .order_by(func.sum(_cost_expr()).desc())
        .all()
    )
    users = {
        user.id: user
        for user in User.query.filter(
            User.id.in_([row[0] for row in rows] or [0])
        )
    }
    return [
        {
            "parent_user_id": parent_user_id,
            "parent": users.get(parent_user_id),
            "calls": int(calls),
            "usd": usd or Decimal("0"),
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
        }
        for parent_user_id, calls, usd, input_tokens, output_tokens in rows
    ]


def totals_by_child(parent_user_id, since=None):
    query = db.session.query(
        KidsAiLlmCall.child_id,
        func.count(KidsAiLlmCall.id),
        func.coalesce(func.sum(_cost_expr()), 0),
        func.coalesce(func.sum(KidsAiLlmCall.input_tokens), 0),
        func.coalesce(func.sum(KidsAiLlmCall.output_tokens), 0),
    ).filter(KidsAiLlmCall.parent_user_id == parent_user_id)
    if since is not None:
        query = query.filter(KidsAiLlmCall.created_at >= since)
    rows = (
        query.group_by(KidsAiLlmCall.child_id)
        .order_by(func.sum(_cost_expr()).desc())
        .all()
    )
    children = {
        child.id: child
        for child in KidsAiChild.query.filter(
            KidsAiChild.id.in_([row[0] for row in rows] or [0])
        )
    }
    return [
        {
            "child": children.get(child_id),
            "child_id": child_id,
            "calls": int(calls),
            "usd": usd or Decimal("0"),
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
        }
        for child_id, calls, usd, input_tokens, output_tokens in rows
    ]


def message_groups(child_id, since=None, limit=50):
    """One row per kid turn that triggered calls, newest first."""
    query = db.session.query(
        KidsAiLlmCall.child_message_id,
        func.min(KidsAiLlmCall.created_at),
        func.count(KidsAiLlmCall.id),
        func.coalesce(func.sum(_cost_expr()), 0),
    ).filter(KidsAiLlmCall.child_id == child_id)
    if since is not None:
        query = query.filter(KidsAiLlmCall.created_at >= since)
    rows = (
        query.group_by(KidsAiLlmCall.child_message_id)
        .order_by(func.min(KidsAiLlmCall.created_at).desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "child_message_id": message_id,
            "first_at": first_at,
            "calls": int(calls),
            "usd": usd or Decimal("0"),
        }
        for message_id, first_at, calls, usd in rows
    ]


def calls_for_message(child_message_id):
    return (
        KidsAiLlmCall.query.filter_by(child_message_id=child_message_id)
        .order_by(KidsAiLlmCall.created_at, KidsAiLlmCall.id)
        .all()
    )


def orphan_calls(child_id, since=None, limit=50):
    query = KidsAiLlmCall.query.filter(
        KidsAiLlmCall.child_id == child_id,
        KidsAiLlmCall.child_message_id.is_(None),
    )
    if since is not None:
        query = query.filter(KidsAiLlmCall.created_at >= since)
    return query.order_by(KidsAiLlmCall.created_at.desc()).limit(limit).all()
