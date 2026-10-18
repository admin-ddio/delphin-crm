from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.request_id import REQUEST_ID_HEADER, accept_or_generate
from app.main import create_app
from tests.conftest import make_settings


def _app(**overrides: object) -> FastAPI:
    app = create_app(make_settings(**overrides))

    @app.post("/api/v1/echo")
    async def echo(request: Request) -> dict[str, int]:
        return {"received": len(await request.body())}

    return app


def test_request_id_generated_and_echoed(client: TestClient) -> None:
    generated = client.get("/healthz").headers[REQUEST_ID_HEADER]
    assert len(generated) == 32
    assert (
        client.get("/healthz", headers={REQUEST_ID_HEADER: "abc-123-xyz"}).headers[
            REQUEST_ID_HEADER
        ]
        == "abc-123-xyz"
    )


def test_malformed_request_id_replaced() -> None:
    assert accept_or_generate("short") != "short"
    assert accept_or_generate("bad id with spaces!") != "bad id with spaces!"
    assert accept_or_generate(None)


def test_security_headers(client: TestClient) -> None:
    headers = client.get("/healthz").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in headers


def test_hsts_in_production() -> None:
    with TestClient(_app(app_env="production")) as client:
        assert "max-age=" in client.get("/healthz").headers["Strict-Transport-Security"]


def test_docs_page_not_given_api_csp(client: TestClient) -> None:
    response = client.get("/api/docs")
    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers


def test_docs_hidden_in_production() -> None:
    with TestClient(_app(app_env="production")) as client:
        assert client.get("/api/docs").status_code == 404
        assert client.get("/api/v1/openapi.json").status_code == 404


def test_untrusted_host_rejected(client: TestClient) -> None:
    assert client.get("/healthz", headers={"Host": "evil.example"}).status_code == 400


def test_body_limit_by_content_length() -> None:
    with TestClient(_app(max_request_body_bytes=1024)) as client:
        response = client.post("/api/v1/echo", content=b"x" * 2048)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


def test_body_limit_when_streamed() -> None:
    def chunks() -> object:
        for _ in range(4):
            yield b"x" * 512

    with TestClient(_app(max_request_body_bytes=1024)) as client:
        response = client.post("/api/v1/echo", content=chunks())
    assert response.status_code == 413


def test_body_within_limit_passes() -> None:
    with TestClient(_app(max_request_body_bytes=1024)) as client:
        assert client.post("/api/v1/echo", content=b"x" * 100).json() == {"received": 100}


class TestCsrf:
    def test_no_session_cookie_no_check(self) -> None:
        with TestClient(_app()) as client:
            assert client.post("/api/v1/echo", content=b"{}").status_code == 200

    def test_session_cookie_without_token_rejected(self) -> None:
        with TestClient(_app()) as client:
            client.cookies.set("delphin_session", "s")
            response = client.post("/api/v1/echo", content=b"{}")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "csrf_failed"

    def test_mismatched_token_rejected(self) -> None:
        with TestClient(_app()) as client:
            client.cookies.set("delphin_session", "s")
            client.cookies.set("delphin_csrf", "token-a")
            response = client.post("/api/v1/echo", headers={"X-CSRF-Token": "token-b"})
        assert response.status_code == 403

    def test_matching_token_accepted(self) -> None:
        with TestClient(_app()) as client:
            client.cookies.set("delphin_session", "s")
            client.cookies.set("delphin_csrf", "token-a")
            response = client.post("/api/v1/echo", headers={"X-CSRF-Token": "token-a"})
        assert response.status_code == 200

    def test_safe_methods_and_exempt_paths_skip_check(self) -> None:
        with TestClient(_app()) as client:
            client.cookies.set("delphin_session", "s")
            assert client.get("/healthz").status_code == 200
            # Exempt (bearer-authenticated): reaches the route and fails auth, not CSRF.
            response = client.post("/api/v1/jobs/run")
        assert response.status_code == 401

    def test_csrf_endpoint_sets_cookie(self) -> None:
        with TestClient(_app()) as client:
            response = client.get("/api/v1/auth/csrf")
        assert response.status_code == 204
        assert "delphin_csrf=" in response.headers["set-cookie"]
        assert "HttpOnly" not in response.headers["set-cookie"]


def test_cors_only_when_configured() -> None:
    with TestClient(_app(cors_origins=["http://localhost:5173"])) as client:
        response = client.options(
            "/api/v1/auth/csrf",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
