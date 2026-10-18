"""The OpenAPI document is the frontend's contract (types are generated from it)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.api.router import MODULE_SLOTS

MODULES_DIR = Path(__file__).resolve().parents[2] / "app" / "modules"
SLOT_FILES = (
    "__init__.py",
    "router.py",
    "schemas.py",
    "service.py",
    "repository.py",
    "models.py",
    "PARITY.md",
)
EXPECTED_SLOTS = [
    "auth",
    "dashboard",
    "notifications",
    "clients",
    "onboarding",
    "projects",
    "tasks",
    "approvals",
    "meetings",
    "services",
    "seo",
    "content",
    "team",
    "documents",
    "reports",
    "finance",
    "search",
    "settings",
    "activity",
    "jobs",
]


def _openapi(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    document: dict[str, Any] = response.json()
    return document


def test_every_module_tag_listed(client: TestClient) -> None:
    tags = [tag["name"] for tag in _openapi(client)["tags"]]
    assert tags == ["health", *EXPECTED_SLOTS]


def test_registered_slots_match_canonical_list() -> None:
    assert [module.TAG["name"] for module in MODULE_SLOTS] == EXPECTED_SLOTS


def test_every_slot_has_its_files() -> None:
    on_disk = sorted(
        p.name for p in MODULES_DIR.iterdir() if p.is_dir() and p.name != "__pycache__"
    )
    assert on_disk == sorted(EXPECTED_SLOTS)
    for slot in EXPECTED_SLOTS:
        for filename in SLOT_FILES:
            assert (MODULES_DIR / slot / filename).is_file(), f"{slot}/{filename} missing"


def test_every_operation_is_tagged_and_named(client: TestClient) -> None:
    seen: set[str] = set()
    for path, item in _openapi(client)["paths"].items():
        for method, operation in item.items():
            assert operation.get("tags"), f"{method.upper()} {path} has no tag"
            op_id = operation.get("operationId")
            assert op_id, f"{method.upper()} {path} has no operationId"
            assert op_id not in seen, f"duplicate operationId {op_id}"
            seen.add(op_id)


def test_api_paths_are_versioned(client: TestClient) -> None:
    for path in _openapi(client)["paths"]:
        assert path in {"/healthz", "/readyz"} or path.startswith("/api/v1/"), path


def test_error_envelope_schema_published(client: TestClient) -> None:
    schemas = _openapi(client)["components"]["schemas"]
    assert set(schemas["ErrorEnvelope"]["properties"]) == {"error"}
    assert {"code", "message", "details", "request_id"} <= set(schemas["ErrorBody"]["properties"])


def test_session_validates_its_body(client: TestClient) -> None:
    response = client.post("/api/v1/auth/session", json={"id_token": "short"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


def test_me_requires_a_session(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_cron_endpoint_requires_bearer_secret(client: TestClient) -> None:
    assert client.post("/api/v1/jobs/run").status_code == 401
    assert (
        client.post("/api/v1/jobs/run", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )
    assert (
        client.post("/api/v1/jobs/run", headers={"Authorization": "Basic abc"}).status_code == 401
    )
    secret = client.app.state.settings.cron_secret.get_secret_value()  # type: ignore[attr-defined]
    response = client.post("/api/v1/jobs/run", headers={"Authorization": f"Bearer {secret}"})
    assert response.status_code == 501


def test_file_download_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/files/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401
