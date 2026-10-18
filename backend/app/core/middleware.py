"""Security middleware: response headers, body size limit, CSRF double-submit check.

All are pure ASGI middleware so they also cover streaming responses.
"""

from __future__ import annotations

from collections.abc import Iterable

from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import cookie_parser
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response
from app.core.security import tokens_match

API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
HSTS = "max-age=63072000; includeSubDomains"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class SecurityHeadersMiddleware:
    """Adds hardening headers unless a route already set them.

    The interactive docs page loads Swagger UI assets, so it is excluded from the
    strict API CSP. Docs are disabled in production unless EXPOSE_DOCS=true.
    """

    def __init__(self, app: ASGIApp, *, production: bool, docs_path: str | None) -> None:
        self.app = app
        self.production = production
        self.docs_path = docs_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_docs = self.docs_path is not None and scope["path"].startswith(self.docs_path)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
                headers.setdefault("X-Frame-Options", "DENY")
                headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
                headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
                if not is_docs:
                    headers.setdefault("Content-Security-Policy", API_CSP)
                if self.production:
                    headers.setdefault("Strict-Transport-Security", HSTS)
            await send(message)

        await self.app(scope, receive, send_with_headers)


class _BodyTooLargeError(Exception):
    pass


class BodySizeLimitMiddleware:
    """Rejects bodies above max_bytes, by Content-Length and while streaming."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = Headers(scope=scope).get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            await self._reject(scope, receive, send)
            return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLargeError
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLargeError:
            if response_started:
                raise
            await self._reject(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = error_response(
            413,
            "payload_too_large",
            "The request body is too large.",
            details={"max_bytes": self.max_bytes},
        )
        await response(scope, receive, send)


class CSRFMiddleware:
    """Double-submit CSRF check for cookie-authenticated mutations.

    A state-changing /api request that carries the session cookie must send the
    CSRF header with the same value as the CSRF cookie. Requests without a
    session cookie (sign-in, bearer-authenticated cron) are not cookie-authenticated
    and pass through. SameSite=Lax cookies are the second line of defence.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        session_cookie: str,
        csrf_cookie: str,
        csrf_header: str,
        exempt_paths: Iterable[str] = (),
        path_prefix: str = "/api/",
    ) -> None:
        self.app = app
        self.session_cookie = session_cookie
        self.csrf_cookie = csrf_cookie
        self.csrf_header = csrf_header
        self.exempt_paths = frozenset(exempt_paths)
        self.path_prefix = path_prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] not in UNSAFE_METHODS
            or not scope["path"].startswith(self.path_prefix)
            or scope["path"] in self.exempt_paths
        ):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        cookies = cookie_parser(headers.get("cookie", ""))
        if self.session_cookie in cookies:
            expected = cookies.get(self.csrf_cookie, "")
            provided = headers.get(self.csrf_header, "")
            if not expected or not provided or not tokens_match(expected, provided):
                response = error_response(
                    403, "csrf_failed", "The CSRF token is missing or invalid."
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
