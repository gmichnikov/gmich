"""Flask CLI for the election board.

Heroku Scheduler should run `flask election2026 pull` every 10 minutes.
"""

import click
from flask.cli import with_appcontext


def init_app(app):
    app.cli.add_command(election2026_cli)


@click.group(name="election2026")
def election2026_cli():
    """Election 2026 commands."""


@election2026_cli.command("pull")
@with_appcontext
def pull_command():
    """Pull Kalshi prices when the newest saved quote is at least a minute old.

    A browser that already pulled inside that minute makes this run a no-op.
    """
    from app.projects.election2026.service import refresh_if_stale

    result = refresh_if_stale()
    if not result["pulled"]:
        click.echo("Skipped. A price was saved less than a minute ago.")
        return
    errors = result["errors"]
    if errors:
        for message in errors:
            click.echo(message, err=True)
        raise click.exceptions.Exit(1)
    click.echo("Pulled Kalshi prices.")
