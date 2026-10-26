"""Security primitives: password hashing, opaque tokens, cookies, login rate limiting.

Sessions follow the pilot's model (ADR-0003): an opaque random token in an
HttpOnly cookie, stored server-side only as its SHA-256 hash. No JWT.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections import deque
from datetime import timedelta
from typing import Protocol

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from starlette.responses import Response

from app.core.clock import Clock, SystemClock
from app.core.config import Settings

_hasher = PasswordHasher()


# ---------------------------------------------------------------- passwords


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# ---------------------------------------------------------------- opaque tokens


def generate_token(nbytes: int = 32) -> str:
    """URL-safe random token for sessions, invites, resets and CSRF."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """SHA-256 hex digest; the only form in which tokens are stored."""
    return hashlib.sha256(token.encode()).hexdigest()


def tokens_match(expected: str, provided: str) -> bool:
    """Constant-time comparison."""
    return hmac.compare_digest(expected.encode(), provided.encode())


# ---------------------------------------------------------------- cookies


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.cookies_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        settings.session_cookie_name,
        httponly=True,
        secure=settings.cookies_secure,
        samesite="lax",
        path="/",
    )


def set_csrf_cookie(response: Response, settings: Settings) -> str:
    """Double-submit token: readable by the SPA, echoed back in the CSRF header."""
    token = generate_token()
    response.set_cookie(
        settings.csrf_cookie_name,
        token,
        httponly=False,
        secure=settings.cookies_secure,
        samesite="lax",
        path="/",
    )
    return token


# ---------------------------------------------------------------- login rate limiting


class LoginRateLimiter(Protocol):
    """Counts FAILED sign-in attempts per account only (pilot fix: successes never count)."""

    async def is_blocked(self, account_key: str) -> bool: ...

    async def record_failure(self, account_key: str) -> None: ...

    async def reset(self, account_key: str) -> None: ...


class InMemoryLoginRateLimiter:
    """Single-process limiter for development and tests.

    Production needs a shared store (DB or Redis) once the auth module is ported;
    see modules/auth/PARITY.md.
    """

    def __init__(
        self,
        *,
        max_failures: int = 5,
        window: timedelta = timedelta(minutes=15),
        clock: Clock | None = None,
    ) -> None:
        self._max_failures = max_failures
        self._window = window
        self._clock: Clock = clock or SystemClock()
        self._failures: dict[str, deque[float]] = {}

    def _prune(self, account_key: str) -> deque[float]:
        now = self._clock.now().timestamp()
        failures = self._failures.setdefault(account_key.lower(), deque())
        while failures and now - failures[0] > self._window.total_seconds():
            failures.popleft()
        return failures

    async def is_blocked(self, account_key: str) -> bool:
        return len(self._prune(account_key)) >= self._max_failures

    async def record_failure(self, account_key: str) -> None:
        self._prune(account_key).append(self._clock.now().timestamp())

    async def reset(self, account_key: str) -> None:
        self._failures.pop(account_key.lower(), None)
