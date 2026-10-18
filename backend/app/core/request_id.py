"""Request correlation: an X-Request-ID on every request, response and log line."""

from __future__ import annotations

import re
import time
from contextvars import ContextVar
from uuid import uuid4

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import get_logger

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{8,128}")
_QUIET_PATHS = frozenset({"/healthz", "/readyz"})

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = get_logger(__name__)


def get_request_id() -> str | None:
    """The current request's ID, or None outside a request."""
    return _request_id.get()


def accept_or_generate(incoming: str | None) -> str:
    """Keep a well-formed incoming ID (from nginx or a client); otherwise mint one."""
    if incoming and _VALID_REQUEST_ID.fullmatch(incoming):
        return incoming
    return uuid4().hex


class RequestContextMiddleware:
    """Outermost app middleware: assigns the request ID and writes one access log line."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = accept_or_generate(Headers(scope=scope).get(REQUEST_ID_HEADER))
        scope.setdefault("state", {})["request_id"] = request_id
        token = _request_id.set(request_id)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        status_code = 500
        started = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            if scope["path"] not in _QUIET_PATHS:
                route = scope.get("route")
                logger.info(
                    "request",
                    method=scope["method"],
                    path=scope["path"],
                    route=getattr(route, "path", None),
                    status=status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                )
            _request_id.reset(token)
            structlog.contextvars.clear_contextvars()
