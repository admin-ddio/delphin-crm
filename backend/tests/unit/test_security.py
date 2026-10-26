from __future__ import annotations

from datetime import UTC, datetime, timedelta

from starlette.responses import Response

from app.core.clock import FixedClock
from app.core.security import (
    InMemoryLoginRateLimiter,
    clear_session_cookie,
    generate_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    set_session_cookie,
    tokens_match,
    verify_password,
)
from tests.conftest import make_settings


def test_password_round_trip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2")
    assert verify_password(hashed, "correct horse battery staple")
    assert not verify_password(hashed, "wrong")
    assert not verify_password("not-a-hash", "anything")
    assert not password_needs_rehash(hashed)


def test_tokens() -> None:
    token = generate_token()
    assert len(token) >= 43
    assert generate_token() != token
    digest = hash_token(token)
    assert len(digest) == 64
    assert digest == hash_token(token)
    assert tokens_match("abc", "abc")
    assert not tokens_match("abc", "abd")


def test_session_cookie_flags() -> None:
    response = Response()
    set_session_cookie(response, "tok", make_settings())
    cookie = response.headers["set-cookie"]
    assert "delphin_session=tok" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" not in cookie

    prod = Response()
    set_session_cookie(prod, "tok", make_settings(app_env="production"))
    assert "Secure" in prod.headers["set-cookie"]

    # Temporary plain-http opt-out (by IP, before TLS); blank means unset.
    insecure = Response()
    set_session_cookie(
        insecure, "tok", make_settings(app_env="production", session_cookie_secure="false")
    )
    assert "Secure" not in insecure.headers["set-cookie"]
    assert make_settings(app_env="production", session_cookie_secure="").cookies_secure
    assert make_settings(session_cookie_secure="true").cookies_secure

    cleared = Response()
    clear_session_cookie(cleared, make_settings())
    assert "Max-Age=0" in cleared.headers["set-cookie"]


async def test_rate_limiter_counts_failures_only_per_account() -> None:
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
    limiter = InMemoryLoginRateLimiter(max_failures=3, window=timedelta(minutes=10), clock=clock)

    for _ in range(2):
        await limiter.record_failure("A@example.test")
    assert not await limiter.is_blocked("a@example.test")
    await limiter.record_failure("a@example.test")
    assert await limiter.is_blocked("a@example.test")
    assert not await limiter.is_blocked("b@example.test")

    clock.advance(timedelta(minutes=11))
    assert not await limiter.is_blocked("a@example.test")

    for _ in range(3):
        await limiter.record_failure("a@example.test")
    await limiter.reset("a@example.test")
    assert not await limiter.is_blocked("a@example.test")
