"""Flask CLI commands for Better Signups project"""

import click
from flask import current_app
from app.projects.better_signups.utils import process_expired_pending_confirmations
import logging

logger = logging.getLogger(__name__)


def init_app(app):
    """Register CLI commands with the Flask app"""

    @app.cli.command("process-waitlist-expirations")
    def process_waitlist_expirations():
        """
        Process expired pending_confirmation signups.
        This command should be run periodically (e.g., every 15 minutes via cron or Heroku Scheduler).

        It finds all pending_confirmation signups that are older than 24 hours,
        deletes them, and offers the spot to the next person on the waitlist.
        """
        click.echo("Starting waitlist expiration processing...")

        with app.app_context():
            result = process_expired_pending_confirmations()

            if result["processed_count"] == 0:
                click.echo("No expired pending confirmations found.")
            else:
                click.echo(
                    f"Found and processed {result['processed_count']} expired pending confirmation(s)."
                )

                if result["cascade_count"] > 0:
                    click.echo(
                        f"  → {result['cascade_count']} spot(s) offered to next person on waitlist"
                    )

                if result["errors"]:
                    click.echo(f"\nErrors encountered ({len(result['errors'])}):")
                    for error in result["errors"]:
                        click.echo(f"  - {error}", err=True)

            click.echo(f"\nProcessing complete:")
            click.echo(f"  - Expired signups removed: {result['processed_count']}")
            click.echo(f"  - Spots offered from waitlist: {result['cascade_count']}")
            click.echo(f"  - Errors: {len(result['errors'])}")
