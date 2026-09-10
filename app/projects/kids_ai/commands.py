"""Flask CLI commands for Kids AI digest and retention."""

import click
from flask.cli import with_appcontext


def init_app(app):
    app.cli.add_command(kids_ai_cli)


@click.group(name="kids-ai")
def kids_ai_cli():
    """Kids AI digest and retention commands."""
    pass


@kids_ai_cli.command("send-digest")
@click.option(
    "--hours",
    default=24,
    show_default=True,
    type=int,
    help="Look back this many hours using conversation modified_at.",
)
@click.option(
    "--parent-id",
    default=None,
    type=int,
    help="Only send for this hub user id.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print who would get mail without sending.",
)
@with_appcontext
def send_digest_command(hours, parent_id, dry_run):
    """
    Email one digest per allowlisted parent with activity in the window.

    Schedule daily at 8:00 America/New_York:
      flask kids-ai send-digest
    """
    from app.models import User
    from app.projects.kids_ai.jobs import collect_digest_activity, run_daily_digest

    if dry_run:
        activity = collect_digest_activity(hours=hours, parent_user_id=parent_id)
        if not activity:
            click.echo("No Kids AI digest activity in the window.")
            return
        for user_id, child_rows in activity.items():
            parent = User.query.get(user_id)
            email = parent.email if parent else f"user {user_id}"
            click.echo(f"\nWould send to {email}:")
            for child, conversations in child_rows:
                click.echo(
                    f"  {child.display_name} (@{child.username}): "
                    f"{len(conversations)} conversation(s)"
                )
                for conversation in conversations:
                    title = conversation.title or "Untitled"
                    flag = " locked" if conversation.locked else ""
                    click.echo(f"    - {title}{flag}")
        click.echo(f"\n{len(activity)} parent(s) would be emailed.")
        return

    result = run_daily_digest(hours=hours, parent_user_id=parent_id, dry_run=False)
    click.echo(
        "Kids AI digest: "
        f"parents={result['parents']} sent={result['sent']} "
        f"failed={result['failed']} skipped={result['skipped']}"
    )


@kids_ai_cli.command("purge-old")
@click.option(
    "--days",
    default=30,
    show_default=True,
    type=int,
    help="Delete conversations with modified_at older than this many days.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Count matching conversations without deleting.",
)
@with_appcontext
def purge_old_command(days, dry_run):
    """
    Hard-delete conversations older than 30 days (default).

    Consent events and API cost rows are kept. Schedule daily:
      flask kids-ai purge-old
    """
    from app.projects.kids_ai.jobs import run_retention

    result = run_retention(days=days, dry_run=dry_run)
    if result["dry_run"]:
        click.echo(
            f"Kids AI retention dry-run: {result['found']} conversation(s) "
            f"older than {days} days."
        )
        return
    click.echo(
        f"Kids AI retention: deleted={result['deleted']} found={result['found']}"
    )
