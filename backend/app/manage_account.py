"""Trusted-operator command to provision the first administrator account.

Run from the backend directory after registering the account:
    python -m app.manage_account user@example.com admin
Use only with trusted database access; never expose this operation as a public API.
"""

import argparse
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User


def main() -> int:
    parser = argparse.ArgumentParser(description="Set a SeatFlow account role using trusted database access.")
    parser.add_argument("email", help="Existing account email")
    parser.add_argument("role", choices=("attendee", "organizer", "admin"))
    args = parser.parse_args()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            print("Account not found. Register the account first.", file=sys.stderr)
            return 1
        user.role = args.role
        db.commit()
        print("Updated role for " + user.email + " to " + user.role)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
