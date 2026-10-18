from __future__ import annotations

from typing import Any

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.errors import (
    BusinessRuleViolation,
    Conflict,
    DomainError,
    Forbidden,
    NotFound,
    NotImplementedYet,
    Unauthorized,
    ValidationFailed,
    error_payload,
)
from app.main import create_app
from tests.conftest import make_settings


class Payload(BaseModel):
    password: str
    count: int


def _app_with_probe_routes(*, production: bool) -> FastAPI:
    settings = make_settings(
        app_env="production" if production else "test",
        allowed_hosts=["testserver"],
    )
    app = create_app(settings)
    probe = APIRouter(prefix="/probe")

    @probe.get("/forbidden")
    async def forbidden() -> None:
        raise Forbidden("Actor lacks clients.update on client 42", details={"client": 42})

    @probe.get("/conflict")
    async def conflict() -> None:
        raise Conflict("Duplicate", details={"field": "domain"})

    @probe.get("/boom")
    async def boom() -> None:
        msg = "secret internal detail"
        raise RuntimeError(msg)

    @probe.post("/validate")
    async def validate(payload: Payload) -> dict[str, Any]:
        return payload.model_dump()

    app.include_router(probe)
    return app


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (Unauthorized, 401, "unauthorized"),
        (Forbidden, 403, "forbidden"),
        (NotFound, 404, "not_found"),
        (Conflict, 409, "conflict"),
        (ValidationFailed, 422, "validation_failed"),
        (BusinessRuleViolation, 422, "business_rule_violation"),
        (NotImplementedYet, 501, "not_implemented"),
    ],
)
def test_domain_error_mapping(exc: type[DomainError], status: int, code: str) -> None:
    assert exc.status_code == status
    assert exc.code == code
    assert exc().message == exc.default_message


def test_error_payload_shape() -> None:
    assert error_payload("conflict", "Nope", details={"a": 1}, request_id="r1") == {
        "error": {"code": "conflict", "message": "Nope", "details": {"a": 1}, "request_id": "r1"}
    }


def test_dev_keeps_messages_and_details() -> None:
    with TestClient(_app_with_probe_routes(production=False)) as client:
        body = client.get("/probe/forbidden").json()
    assert body["error"]["message"] == "Actor lacks clients.update on client 42"
    assert body["error"]["details"] == {"client": 42}
    assert body["error"]["request_id"]


def test_production_redacts_forbidden() -> None:
    with TestClient(_app_with_probe_routes(production=True)) as client:
        response = client.get("/probe/forbidden")
    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "forbidden",
        "message": Forbidden.default_message,
        "details": {},
        "request_id": response.headers["X-Request-ID"],
    }


def test_production_keeps_non_redactable_messages() -> None:
    with TestClient(_app_with_probe_routes(production=True)) as client:
        body = client.get("/probe/conflict").json()
    assert body["error"]["message"] == "Duplicate"


@pytest.mark.parametrize("production", [True, False])
def test_unexpected_errors_never_leak(production: bool) -> None:
    app = _app_with_probe_routes(production=production)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/probe/boom")
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text
    assert error["details"] == ({} if production else {"exception": "RuntimeError"})


def test_validation_errors_do_not_echo_input() -> None:
    with TestClient(_app_with_probe_routes(production=False)) as client:
        response = client.post("/probe/validate", json={"password": "hunter2", "count": "x"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert "hunter2" not in response.text


def test_http_errors_use_envelope(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
