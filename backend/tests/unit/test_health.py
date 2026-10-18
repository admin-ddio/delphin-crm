from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.health import expected_heads


def test_liveness(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_single_migration_head() -> None:
    assert len(expected_heads()) == 1
