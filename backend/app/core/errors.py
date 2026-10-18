"""Domain exceptions and the single error envelope used by every response.

Shape: {"error": {"code", "message", "details", "request_id"}}.
In production, redactable errors (401/403) and every unexpected error lose their
internal message and details. This mirrors the pilot's `forbidden()` redaction.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.request_id import get_request_id

logger = get_logger(__name__)

_SERVER_ERROR = 500


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorEnvelope(BaseModel):
    """The only error shape the API ever returns."""

    error: ErrorBody


class DomainError(Exception):
    status_code: ClassVar[int] = 400
    code: ClassVar[str] = "bad_request"
    default_message: ClassVar[str] = "The request could not be processed."
    redact_in_production: ClassVar[bool] = False

    def __init__(
        self, message: str | None = None, *, details: Mapping[str, Any] | None = None
    ) -> None:
        self.message = message or self.default_message
        self.details: dict[str, Any] = dict(details or {})
        super().__init__(self.message)


class Unauthorized(DomainError):
    status_code = 401
    code = "unauthorized"
    default_message = "Authentication required."
    redact_in_production = True


class Forbidden(DomainError):
    status_code = 403
    code = "forbidden"
    default_message = "You do not have permission to perform this action."
    redact_in_production = True


class NotFound(DomainError):
    status_code = 404
    code = "not_found"
    default_message = "The requested resource was not found."


class Conflict(DomainError):
    status_code = 409
    code = "conflict"
    default_message = "The request conflicts with the current state of the resource."


class ValidationFailed(DomainError):
    status_code = 422
    code = "validation_failed"
    default_message = "The submitted data is invalid."


class BusinessRuleViolation(DomainError):
    status_code = 422
    code = "business_rule_violation"
    default_message = "The request breaks a business rule."


class RateLimited(DomainError):
    status_code = 429
    code = "rate_limited"
    default_message = "Too many attempts. Try again later."


class NotImplementedYet(DomainError):
    """Raised by scaffold stubs until the pilot feature is ported."""

    status_code = 501
    code = "not_implemented"
    default_message = "This endpoint has not been ported from the pilot yet."


HTTP_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    406: "not_acceptable",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_failed",
    429: "rate_limited",
    501: "not_implemented",
    503: "service_unavailable",
}

AUTH_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope, "description": "Authentication required"},
    403: {"model": ErrorEnvelope, "description": "Permission denied"},
}
NOT_PORTED_RESPONSE: dict[int | str, dict[str, Any]] = {
    501: {"model": ErrorEnvelope, "description": "Not yet ported from the pilot"},
}


def _request_id_of(request: Request) -> str | None:
    return getattr(request.state, "request_id", None) or get_request_id()


def error_payload(
    code: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    body = ErrorBody(code=code, message=message, details=dict(details or {}), request_id=request_id)
    return ErrorEnvelope(error=body).model_dump(mode="json")


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
    request_id: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_payload(
            code, message, details=details, request_id=request_id or get_request_id()
        ),
        headers=dict(headers) if headers else None,
    )


def install_exception_handlers(app: FastAPI, settings: Settings) -> None:
    production = settings.is_production

    async def handle_domain_error(request: Request, exc: Exception) -> Response:
        assert isinstance(exc, DomainError)  # noqa: S101
        message, details = exc.message, exc.details
        if production and exc.redact_in_production:
            message, details = exc.default_message, {}
        return error_response(
            exc.status_code, exc.code, message, details=details, request_id=_request_id_of(request)
        )

    async def handle_http_error(request: Request, exc: Exception) -> Response:
        assert isinstance(exc, StarletteHTTPException)  # noqa: S101
        code = HTTP_STATUS_CODES.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ")
        if production and exc.status_code >= _SERVER_ERROR:
            message = "The service is temporarily unavailable."
        return error_response(
            exc.status_code,
            code,
            message,
            request_id=_request_id_of(request),
            headers=exc.headers,
        )

    async def handle_validation_error(request: Request, exc: Exception) -> Response:
        assert isinstance(exc, RequestValidationError)  # noqa: S101
        # Never echo submitted values back: they may contain passwords or tokens.
        errors = [
            {
                "loc": list(err.get("loc", ())),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        return error_response(
            422,
            ValidationFailed.code,
            ValidationFailed.default_message,
            details={"errors": jsonable_encoder(errors)},
            request_id=_request_id_of(request),
        )

    async def handle_unexpected_error(request: Request, exc: Exception) -> Response:
        logger.exception("unhandled_error", exc_type=type(exc).__name__)
        details = {} if production else {"exception": type(exc).__name__}
        return error_response(
            _SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred.",
            details=details,
            request_id=_request_id_of(request),
        )

    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
