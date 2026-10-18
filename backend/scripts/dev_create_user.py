"""DEV/TEST ONLY: a ready-to-use account in the Firebase Auth Emulator and the app.

Creates (or updates) the Firebase user with a password and a VERIFIED e-mail,
then the app user with that uid and role. Used for local sign-in and Playwright.
Refuses to run against a real Firebase project or with APP_ENV=production;
real users are invited (scripts/create_super_admin.py).

Usage:
    docker compose run --rm backend python scripts/dev_create_user.py \\
        dev@example.com "Dev Admin" super_admin 'a-long-dev-password' [--unverified]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime

from firebase_admin import auth as firebase_auth
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db.session import create_sessionmaker
from app.platform.identity.firebase import firebase_app
from app.platform.identity.models import Role, User, UserRole

MIN_PASSWORD = 6  # Firebase's own minimum; the emulator enforces it.


def upsert_firebase_user(
    project_id: str, email: str, full_name: str, password: str, *, verified: bool
) -> str:
    app = firebase_app(project_id)
    try:
        record = firebase_auth.get_user_by_email(email, app=app)
        firebase_auth.update_user(
            record.uid,
            password=password,
            display_name=full_name,
            email_verified=verified,
            disabled=False,
            app=app,
        )
        return str(record.uid)
    except firebase_auth.UserNotFoundError:
        record = firebase_auth.create_user(
            email=email,
            password=password,
            display_name=full_name,
            email_verified=verified,
            app=app,
        )
        return str(record.uid)


async def upsert(
    email: str, full_name: str, role_key: str, password: str, *, verified: bool
) -> int:
    settings = get_settings()
    if settings.is_production or not os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"):
        print("refusing to run: dev/test only (needs FIREBASE_AUTH_EMULATOR_HOST)", file=sys.stderr)
        return 2
    uid = upsert_firebase_user(
        settings.firebase_project_id, email, full_name, password, verified=verified
    )
    engine = create_async_engine(settings.database_url)
    try:
        async with create_sessionmaker(engine)() as session, session.begin():
            role = (
                await session.execute(select(Role).where(Role.key == role_key))
            ).scalar_one_or_none()
            if role is None:
                print(f"role '{role_key}' missing: run scripts/seed_config.py", file=sys.stderr)
                return 1
            user = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if user is None:
                user = User(email=email, full_name=full_name)
                session.add(user)
            user.full_name = full_name
            user.firebase_uid = uid
            user.is_active = True
            user.activated_at = user.activated_at or datetime.now(UTC)
            user.approved_at = user.approved_at or datetime.now(UTC)
            await session.flush()
            await session.execute(delete(UserRole).where(UserRole.user_id == user.id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
    finally:
        await engine.dispose()
    state = "verified" if verified else "UNVERIFIED"
    print(f"dev user ready: {email} ({role_key}, e-mail {state}, firebase uid {uid})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("full_name")
    parser.add_argument("role")
    parser.add_argument("password")
    parser.add_argument("--unverified", action="store_true", help="leave the e-mail unverified")
    args = parser.parse_args(argv)
    if len(args.password) < MIN_PASSWORD:
        print(f"password must be at least {MIN_PASSWORD} characters", file=sys.stderr)
        return 1
    return asyncio.run(
        upsert(args.email, args.full_name, args.role, args.password, verified=not args.unverified)
    )


if __name__ == "__main__":
    sys.exit(main())
