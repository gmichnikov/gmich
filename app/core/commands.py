"""Flask CLI commands for hub-level credit administration."""

import click
from flask.cli import with_appcontext


def init_app(app):
    app.cli.add_command(credits_cli)


@click.group(name="credits")
def credits_cli():
    """Credit balance commands."""
    pass


@credits_cli.command("test-alert")
@click.option("--email", required=True, help="User to describe in the test alert.")
@with_appcontext
def test_alert_command(email):
    """Send the out-of-credits admin alert without changing any balances."""
    from app.models import User
    from app.utils.credit_alerts import notify_admin_credits_exhausted

    user = User.query.filter(User.email.ilike(email)).first()
    if not user:
        raise click.ClickException(f"No user with email: {email}")

    response = notify_admin_credits_exhausted(
        user.email,
        user.short_name or user.full_name or user.email,
        "a manual test",
    )
    if response is None:
        raise click.ClickException(
            "Alert was not sent. Check ADMIN_EMAIL and the Mailgun settings."
        )
    click.echo(f"Test alert sent for {user.email}.")


@credits_cli.command("low-balances")
@click.option("--threshold", default=5, show_default=True, help="Flag balances at or below this.")
@with_appcontext
def low_balances_command(threshold):
    """List users at or below a credit threshold."""
    from app.models import User

    users = (
        User.query.filter(User.credits <= threshold)
        .order_by(User.credits, User.email)
        .all()
    )
    if not users:
        click.echo(f"No users at or below {threshold} credits.")
        return

    for user in users:
        state = "OUT" if (user.credits or 0) <= 0 else "low"
        click.echo(f"{state:>3}  {user.credits:>4}  {user.email}")
