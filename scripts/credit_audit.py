"""Print per-user credit balances and derived usage.

Same numbers as the /admin/users page, for when you'd rather read them in a
terminal (e.g. `heroku run python scripts/credit_audit.py`). Read-only.
"""

import pytz

from run import app
from app.core.admin import (
    RECENT_ACTIVITY_DAYS,
    decorate_users_with_credits,
)
from app.models import User


def main():
    with app.app_context():
        users = User.query.order_by(User.email).all()
        decorate_users_with_credits(users, pytz.utc)
        users.sort(key=lambda u: (-u.credit_consumed, u.email))

        print(f"{len(users)} users\n")

        for user in users:
            print(user.email)
            print(
                f"   balance={user.credits}  granted={user.credit_granted} "
                f"(10 default + {user.credit_added} added)  consumed={user.credit_consumed}"
            )
            breakdown = (
                ", ".join(
                    f"{label}={count}" for label, count, _recent in user.credit_breakdown
                )
                or "none recorded"
            )
            print(f"   activity: {breakdown}")
            print(
                f"   last {RECENT_ACTIVITY_DAYS}d events={user.credit_recent_events}  "
                f"last activity={user.credit_last_activity_display or 'never'}"
            )
            if user.credit_no_credit_skips or user.credit_failed_sends:
                print(
                    f"   !! daily emails skipped for no credits="
                    f"{user.credit_no_credit_skips}  failed sends={user.credit_failed_sends}"
                )
            print()

        out_of_credits = [u for u in users if (u.credits or 0) <= 0]
        low = [u for u in users if 0 < (u.credits or 0) <= 5]

        print("=== out of credits ===")
        for user in out_of_credits:
            print(f"   {user.email}  skipped_emails={user.credit_no_credit_skips}")
        if not out_of_credits:
            print("   none")

        print("\n=== low (1-5 credits) ===")
        for user in low:
            print(f"   {user.email}  balance={user.credits}")
        if not low:
            print("   none")


if __name__ == "__main__":
    main()
