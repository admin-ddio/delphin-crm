"""Create the first Super Admin and print a one-time password-setup link (never a password).

Creates the user in Firebase Auth (no password yet) and in the app with the
super_admin role. Opening the link lets them choose a password; on first sign-in
Firebase asks them to verify their e-mail. Run `scripts/seed_config.py` first.

Real projects need GOOGLE_APPLICATION_CREDENTIALS (a service-account key) to
create Firebase users; with FIREBASE_AUTH_EMULATOR_HOST set it uses the emulator.

Usage:
    docker compose run --rm backend python scripts/create_super_admin.py \\
        admin@example.com "Full Name"
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.ext.asyncio import create_async_engine

from app.authz.permissions import SUPER_ADMIN
from app.core.clock import SystemClock
from app.core.config import get_settings
from app.core.errors import DomainError
from app.db.session import create_sessionmaker
from app.modules.auth.service import AuthService
from app.platform.identity.firebase import FirebaseIdentityProvider


async def create(email: str, full_name: str) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with create_sessionmaker(engine)() as session, session.begin():
            service = AuthService(
                session,
                clock=SystemClock(),
                settings=settings,
                identity=FirebaseIdentityProvider(settings.firebase_project_id),
            )
            invitation = await service.invite(
                email=email, full_name=full_name, role_key=SUPER_ADMIN
            )
    except DomainError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    print(f"Super Admin {email} created.")
    print("Send them this one-time link to choose a password:")
    print(invitation.link)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("full_name")
    args = parser.parse_args(argv)
    try:
        email = validate_email(args.email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        print(f"invalid e-mail: {exc}", file=sys.stderr)
        return 1
    return asyncio.run(create(email, args.full_name.strip()))


if __name__ == "__main__":
    sys.exit(main())
