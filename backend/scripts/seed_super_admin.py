"""Seed a Super Admin who can sign in straight away with an e-mail and password.

Idempotent. Seeds the default roles, then creates (or updates) the Firebase account
with the given password and a VERIFIED e-mail, and the app user with the
super_admin role. Re-running it resets the password, unlocks the account and
re-links it to the current Firebase project (e.g. after a user was created in the
emulator by mistake).

The password is read from SUPER_ADMIN_PASSWORD or prompted for, never taken from
the command line, so it stays out of shell history and the process list.

A real Firebase project needs GOOGLE_APPLICATION_CREDENTIALS (a service-account
key) to manage users; with FIREBASE_AUTH_EMULATOR_HOST set it uses the emulator.

Usage (production; prompts for the password):
    docker compose -f compose.yaml -f compose.prod.yaml run --rm \\
        -v /path/to/service-account.json:/run/secrets/firebase.json:ro \\
        -e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/firebase.json \\
        backend python scripts/seed_super_admin.py admin@example.com "Full Name"
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from datetime import UTC, datetime

from email_validator import EmailNotValidError, validate_email
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError
from seed_config import main as seed_roles
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.authz.permissions import SUPER_ADMIN
from app.core.config import get_settings
from app.db.session import create_sessionmaker
from app.platform.audit.service import AuditWriter
from app.platform.identity.firebase import firebase_app
from app.platform.identity.models import Role, User, UserRole

PASSWORD_ENV = "SUPER_ADMIN_PASSWORD"  # noqa: S105 (variable name, not a secret)
MIN_PASSWORD = 8
MIN_PASSWORD_PRODUCTION = 12


def read_password(min_length: int) -> str | None:
    password = os.environ.get(PASSWORD_ENV)
    if password is None:
        if not sys.stdin.isatty():
            print(f"no terminal: set {PASSWORD_ENV} instead", file=sys.stderr)
            return None
        password = getpass.getpass("Password: ")
        if getpass.getpass("Repeat password: ") != password:
            print("passwords do not match", file=sys.stderr)
            return None
    if len(password) < min_length:
        print(f"password must be at least {min_length} characters", file=sys.stderr)
        return None
    return password


def upsert_firebase_user(project_id: str, email: str, full_name: str, password: str) -> str:
    app = firebase_app(project_id)
    try:
        record = firebase_auth.get_user_by_email(email, app=app)
    except firebase_auth.UserNotFoundError:
        record = firebase_auth.create_user(
            email=email,
            password=password,
            display_name=full_name,
            email_verified=True,
            app=app,
        )
        return str(record.uid)
    firebase_auth.update_user(
        record.uid,
        password=password,
        display_name=full_name,
        email_verified=True,
        disabled=False,
        app=app,
    )
    return str(record.uid)


async def upsert_app_user(database_url: str, email: str, full_name: str, uid: str) -> int:
    engine = create_async_engine(database_url)
    try:
        async with create_sessionmaker(engine)() as session, session.begin():
            role = (await session.execute(select(Role).where(Role.key == SUPER_ADMIN))).scalar_one()
            holder = (
                await session.execute(select(User).where(User.firebase_uid == uid))
            ).scalar_one_or_none()
            if holder is not None and holder.email.lower() != email.lower():
                print(f"Firebase account {uid} is linked to {holder.email}", file=sys.stderr)
                return 1
            user = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            created = user is None
            if user is None:
                user = User(email=email, full_name=full_name)
                session.add(user)
            now = datetime.now(UTC)
            user.full_name = full_name
            user.firebase_uid = uid
            user.is_active = True
            user.approved_at = user.approved_at or now
            user.activated_at = user.activated_at or now
            user.failed_login_count = 0
            user.locked_until = None
            await session.flush()
            await session.execute(delete(UserRole).where(UserRole.user_id == user.id))
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await AuditWriter(session).record(
                action="auth.super_admin_seeded",
                entity_type="user",
                entity_id=user.id,
                context={"created": created},
            )
    finally:
        await engine.dispose()
    return 0


async def run(email: str, full_name: str) -> int:
    settings = get_settings()
    password = read_password(MIN_PASSWORD_PRODUCTION if settings.is_production else MIN_PASSWORD)
    if password is None:
        return 1
    if await seed_roles() != 0:
        return 1
    try:
        uid = await asyncio.to_thread(
            upsert_firebase_user, settings.firebase_project_id, email, full_name, password
        )
    except (FirebaseError, ValueError) as exc:
        print(f"Firebase: {exc}", file=sys.stderr)
        if not os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"):
            print("check GOOGLE_APPLICATION_CREDENTIALS and FIREBASE_PROJECT_ID", file=sys.stderr)
        return 1
    if await upsert_app_user(settings.database_url, email, full_name, uid) != 0:
        return 1
    target = (
        "the Firebase Auth Emulator"
        if os.environ.get("FIREBASE_AUTH_EMULATOR_HOST")
        else f"Firebase project {settings.firebase_project_id}"
    )
    login_url = f"{settings.app_base_url.rstrip('/')}/login"
    print(f"Super Admin ready: {email} ({target}). Sign in at {login_url}")
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
    return asyncio.run(run(email, args.full_name.strip()))


if __name__ == "__main__":
    sys.exit(main())
