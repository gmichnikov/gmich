"""Flask CLI commands for the Helper project."""

import os
import uuid
from datetime import date, datetime, timedelta

import click
from flask import current_app
from flask.cli import with_appcontext

from app import db


def init_app(app):
    app.cli.add_command(helper_cli)


@click.group(name="helper")
def helper_cli():
    """Helper project commands."""
    pass


@helper_cli.command("send-reminders")
@click.option(
    "--limit",
    default=100,
    show_default=True,
    help="Max reminders to process in one run.",
)
@with_appcontext
def send_reminders_command(limit):
    """
    Send due task reminder emails (Heroku Scheduler / cron).

    Run: flask helper send-reminders
    """
    from app.projects.helper.reminder_dispatch import run_pending_reminders

    result = run_pending_reminders(limit=limit)
    click.echo(
        f"candidates={result['candidates']} sent={result['sent']} failed={result['failed']}"
    )


def _seed_inbound_email(domain: str, group_id: int, user_id: int, **kwargs) -> str:
    """Insert one inbound row + optional action log; return idempotency key used."""
    from app.projects.helper.models import HelperActionLog, HelperInboundEmail

    key = f"seed-{uuid.uuid4().hex}"
    inbound = HelperInboundEmail(
        idempotency_key=key,
        recipient=kwargs.get("recipient", f"seed-local@{domain}"),
        sender_raw=kwargs.get("sender_raw", "seed@local.test"),
        sender_user_id=kwargs.get("sender_user_id", user_id),
        group_id=group_id,
        subject=kwargs.get("subject"),
        body_text=kwargs.get("body_text"),
        status=kwargs.get("status", "processed"),
        signature_valid=True,
    )
    db.session.add(inbound)
    db.session.flush()
    for action in kwargs.get("actions", []):
        db.session.add(
            HelperActionLog(
                inbound_email_id=inbound.id,
                action_type=action["type"],
                detail=action.get("detail"),
                error_message=action.get("error"),
            )
        )
    return key


@helper_cli.command("seed")
@click.option(
    "--user-email",
    default=None,
    help="Existing user to add as group member (default: ADMIN_EMAIL or first user).",
)
@click.option(
    "--clear",
    is_flag=True,
    help="Remove the previous seed group (same inbound address) before creating.",
)
@with_appcontext
def seed_command(user_email, clear):
    """
    Insert demo Helper data for local UI testing (no Mailgun).

    Creates a group \"Demo Family (local)\" at seed-local@<CUSTOM_DOMAIN>,
    several open and completed tasks, and sample inbound + action log rows.

    Run: flask helper seed
    """
    from app.models import User
    from app.projects.helper.models import (
        HelperActionLog,
        HelperGroup,
        HelperGroupMember,
        HelperInboundEmail,
        HelperTask,
    )

    domain = (current_app.config.get("CUSTOM_DOMAIN") or os.getenv("CUSTOM_DOMAIN") or "").strip()
    if not domain:
        domain = "helper.local.test"
        click.echo(f"Warning: CUSTOM_DOMAIN not set; using inbound seed-local@{domain}")

    inbound_addr = f"seed-local@{domain}"

    existing = HelperGroup.query.filter(
        db.func.lower(HelperGroup.inbound_email) == inbound_addr.lower()
    ).first()

    if existing and not clear:
        click.echo(
            f"Seed group already exists ({inbound_addr}). "
            f"Use --clear to remove it and re-seed, or visit /helper/."
        )
        return

    if existing and clear:
        _delete_seed_group(existing)

    # Resolve user
    if user_email:
        user = User.query.filter(
            db.func.lower(User.email) == user_email.strip().lower()
        ).first()
        if not user:
            raise click.ClickException(f"No user with email: {user_email}")
    else:
        admin = current_app.config.get("ADMIN_EMAIL") or os.getenv("ADMIN_EMAIL")
        user = None
        if admin:
            user = User.query.filter(db.func.lower(User.email) == admin.lower()).first()
        if not user:
            user = User.query.order_by(User.id).first()
        if not user:
            raise click.ClickException(
                "No users in database. Create an account first, or pass --user-email."
            )

    group = HelperGroup(
        name="Demo Family (local)",
        inbound_email=inbound_addr.lower(),
        created_by_user_id=user.id,
    )
    db.session.add(group)
    db.session.flush()

    db.session.add(HelperGroupMember(group_id=group.id, user_id=user.id))

    today = date.today()
    open_specs = [
        {
            "title": "Register for spring soccer",
            "due_date": today + timedelta(days=7),
            "notes": "League site: example.org/register. Fee $85 due at signup.",
            "assignee": user.id,
        },
        {
            "title": "Schedule dentist cleanings",
            "due_date": None,
            "notes": None,
            "assignee": None,
        },
        {
            "title": "Return library books",
            "due_date": today + timedelta(days=3),
            "notes": "3 books on the kitchen counter.",
            "assignee": user.id,
        },
    ]
    for spec in open_specs:
        db.session.add(
            HelperTask(
                group_id=group.id,
                title=spec["title"],
                due_date=spec["due_date"],
                notes=spec["notes"],
                assignee_user_id=spec["assignee"],
                created_by_user_id=user.id,
                status="open",
            )
        )

    done_specs = [
        {"title": "Buy birthday gift for Alex", "days_ago": 2},
        {"title": "Pay utility bill", "days_ago": 5},
    ]
    for spec in done_specs:
        completed = datetime.utcnow() - timedelta(days=spec["days_ago"])
        db.session.add(
            HelperTask(
                group_id=group.id,
                title=spec["title"],
                due_date=None,
                notes=None,
                assignee_user_id=user.id,
                created_by_user_id=user.id,
                status="complete",
                completed_by_user_id=user.id,
                completed_at=completed,
            )
        )

    db.session.flush()

    from app.projects.helper.reminder_logic import sync_reminder_with_due_date

    for t in HelperTask.query.filter_by(group_id=group.id, status="open").all():
        sync_reminder_with_due_date(t)

    # Sample inbound + logs (for admin log UIs)
    _seed_inbound_email(
        domain,
        group.id,
        user.id,
        subject="Buy milk",
        body_text="Please pick up 2% on the way home.",
        status="processed",
        actions=[
            {"type": "task_created", "detail": {"title": "Buy milk"}},
            {"type": "confirmation_sent", "detail": {"to": user.email}},
        ],
    )
    _seed_inbound_email(
        domain,
        group.id,
        user.id,
        subject="",
        body_text="",
        status="empty_content",
        actions=[{"type": "empty_content"}],
    )
    _seed_inbound_email(
        domain,
        group.id,
        None,
        subject="Spam attempt",
        body_text="Hello",
        sender_raw="stranger@example.com",
        sender_user_id=None,
        status="sender_not_allowed",
        actions=[{"type": "sender_unknown_user", "detail": {"sender": "stranger@example.com"}}],
    )

    db.session.commit()

    click.echo(
        f"Helper seed data created.\n"
        f"  Group: {group.name} (id={group.id})\n"
        f"  Inbound: {inbound_addr}\n"
        f"  Member: {user.email}\n"
        f"  Log in as that user and open /helper/"
    )


@helper_cli.command("eval-router")
@click.option(
    "--fixture-file",
    default=None,
    help="Path to fixture JSON file. Defaults to the bundled router_fixtures.json.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Run evals and print results but do not write to the database.",
)
@with_appcontext
def eval_router_command(fixture_file, dry_run):
    """
    Run the router eval suite against Claude and record results.

    Each fixture in the JSON file is sent through route_email() and the
    actual route is compared against expected_route. Results are saved to
    helper_eval_run / helper_eval_result tables.

    Run: flask helper eval-router
    """
    import json
    import time as time_mod
    import os

    from app.projects.helper.claude import CLAUDE_MODEL, ClaudeResponseError, route_email
    from app.projects.helper.models import HelperEvalResult, HelperEvalRun

    if fixture_file is None:
        fixture_file = os.path.join(
            os.path.dirname(__file__), "evals", "router_fixtures.json"
        )

    with open(fixture_file) as f:
        fixtures = json.load(f)

    # Fake member list — good enough for routing classification
    fake_members = [
        ("Greg M.", "greg@example.com"),
        ("Alex M.", "alex@example.com"),
    ]
    fake_sender_tz = "America/New_York"

    click.echo(f"Running {len(fixtures)} router fixtures against {CLAUDE_MODEL}...")

    run = HelperEvalRun(
        model=CLAUDE_MODEL,
        fixture_file=os.path.basename(fixture_file),
        total=len(fixtures),
    )
    if not dry_run:
        db.session.add(run)
        db.session.flush()

    passed = failed = errored = 0
    result_rows = []

    for fixture in fixtures:
        fid = fixture["id"]
        expected = fixture["expected_route"]
        subject = fixture.get("subject", "")
        body = fixture.get("body", "")
        open_tasks = fixture.get("open_tasks") or []

        t0 = time_mod.monotonic()
        actual_route = None
        raw_response = None
        error_message = None

        try:
            router_result = route_email(
                subject=subject,
                body=body,
                member_names_emails=fake_members,
                sender_tz=fake_sender_tz,
                open_tasks=open_tasks,
            )
            actual_route = router_result.get("route", "")
            raw_response = str(router_result)
        except ClaudeResponseError as e:
            error_message = str(e)
            raw_response = e.raw_response
            errored += 1
        except Exception as e:
            error_message = str(e)
            errored += 1

        latency_ms = int((time_mod.monotonic() - t0) * 1000)
        ok = (actual_route == expected) and error_message is None

        if ok:
            passed += 1
            status_label = click.style("PASS", fg="green")
        elif error_message:
            status_label = click.style("ERR ", fg="red")
        else:
            failed += 1
            status_label = click.style("FAIL", fg="red")

        click.echo(
            f"  [{status_label}] {fid:<40} expected={expected:<15} actual={actual_route or error_message or '—'} ({latency_ms}ms)"
        )

        result_rows.append(
            HelperEvalResult(
                run_id=run.id if not dry_run else 0,
                fixture_id=fid,
                description=fixture.get("description"),
                expected_route=expected,
                actual_route=actual_route,
                passed=ok,
                raw_response=str(raw_response)[:4000] if raw_response else None,
                error_message=error_message,
                latency_ms=latency_ms,
            )
        )

    run.passed = passed
    run.failed = failed
    run.errored = errored

    if not dry_run:
        for r in result_rows:
            r.run_id = run.id
            db.session.add(r)
        db.session.commit()
        click.echo(f"\nResults saved (run id={run.id}).")
    else:
        click.echo("\n[dry-run] Results not saved.")

    pass_rate = int(100 * passed / len(fixtures)) if fixtures else 0
    click.echo(
        f"\nTotal: {len(fixtures)}  Passed: {passed}  Failed: {failed}  Errored: {errored}  ({pass_rate}%)"
    )

    if failed or errored:
        raise SystemExit(1)


def _delete_seed_group(group):
    from app.projects.helper.models import (
        HelperActionLog,
        HelperGroupMember,
        HelperInboundEmail,
        HelperTask,
    )

    for t in HelperTask.query.filter_by(group_id=group.id).all():
        t.source_inbound_email_id = None
        t.completed_via_inbound_email_id = None
    db.session.flush()

    for inbound in HelperInboundEmail.query.filter_by(group_id=group.id).all():
        HelperActionLog.query.filter_by(inbound_email_id=inbound.id).delete(
            synchronize_session=False
        )
        db.session.delete(inbound)
    db.session.flush()

    HelperTask.query.filter_by(group_id=group.id).delete(synchronize_session=False)
    HelperGroupMember.query.filter_by(group_id=group.id).delete(synchronize_session=False)
    db.session.delete(group)
    db.session.commit()
    click.echo(f"Removed seed group id={group.id}.")
