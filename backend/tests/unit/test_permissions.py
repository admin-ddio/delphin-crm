from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.authz import permissions as perms
from app.authz.actor import Actor
from app.authz.dependencies import (
    get_actor,
    require_any,
    require_permission,
)
from app.main import create_app
from tests.conftest import make_settings


def make_actor(*permissions: str) -> Actor:
    return Actor(
        user_id=uuid.uuid4(),
        email="user@example.test",
        full_name="Test User",
        roles=frozenset({"test"}),
        permissions=frozenset(permissions),
    )


def test_wildcard_grants_everything() -> None:
    actor = make_actor(perms.WILDCARD)
    assert actor.is_super_admin
    assert actor.can("clients.create")
    assert actor.can_all("clients.create", "finance.read")


def test_explicit_permissions() -> None:
    actor = make_actor("clients.read")
    assert not actor.is_super_admin
    assert actor.can("clients.read")
    assert not actor.can("clients.create")
    assert actor.can_any("clients.create", "clients.read")
    assert not actor.can_all("clients.create", "clients.read")


@pytest.mark.parametrize("name", ["clients.create", "settings.roles.manage", "*"])
def test_validate_permission_accepts(name: str) -> None:
    assert perms.validate_permission(name) == name


@pytest.mark.parametrize("name", ["", "clients", "Clients.Create", "clients.", ".create", "a b.c"])
def test_validate_permission_rejects(name: str) -> None:
    with pytest.raises(ValueError, match="Malformed"):
        perms.validate_permission(name)


def test_unknown_permission_rejected_once_catalogue_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(perms, "CATALOGUE", frozenset({"clients.read"}))
    # Interim (demo) catalogue: format only.
    assert perms.validate_permission("clients.delete") == "clients.delete"
    monkeypatch.setattr(perms, "CATALOGUE_SOURCE", "pilot")
    assert perms.validate_permission("clients.read") == "clients.read"
    with pytest.raises(ValueError, match="Unknown permission"):
        perms.validate_permission("clients.delete")


def test_default_roles() -> None:
    keys = [role.key for role in perms.DEFAULT_ROLES]
    assert len(keys) == len(set(keys))
    assert keys[0] == perms.SUPER_ADMIN
    assert perms.DEFAULT_ROLES[0].permissions == frozenset({perms.WILDCARD})
    for role in perms.DEFAULT_ROLES:
        for permission in role.permissions:
            perms.validate_permission(permission)
            assert permission == perms.WILDCARD or permission in perms.CATALOGUE


@pytest.mark.skipif(not perms.is_catalogue_ported(), reason="permissions.ts not yet ported")
def test_catalogue_ported_from_pilot() -> None:
    assert perms.CATALOGUE
    non_super = [r for r in perms.DEFAULT_ROLES if r.key != perms.SUPER_ADMIN]
    assert all(role.permissions for role in non_super)


def test_require_any_needs_arguments() -> None:
    with pytest.raises(ValueError, match="at least one"):
        require_any()


def test_require_permission_validates_at_definition() -> None:
    with pytest.raises(ValueError, match="Malformed"):
        require_permission("not a permission")


@pytest.fixture
def guarded_client() -> Iterator[tuple[FastAPI, TestClient]]:
    app = create_app(make_settings())

    @app.get("/guarded/one", dependencies=[Depends(require_permission("clients.read"))])
    async def one() -> dict[str, bool]:
        return {"ok": True}

    @app.get(
        "/guarded/any",
        dependencies=[Depends(require_any("clients.read", "clients.create"))],
    )
    async def any_of() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        yield app, client


@pytest.mark.parametrize("path", ["/guarded/one", "/guarded/any"])
def test_guard_allows_and_denies(guarded_client: tuple[FastAPI, TestClient], path: str) -> None:
    app, client = guarded_client
    app.dependency_overrides[get_actor] = lambda: make_actor("clients.read")
    assert client.get(path).status_code == 200
    app.dependency_overrides[get_actor] = lambda: make_actor("finance.read")
    response = client.get(path)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_missing_session_cookie_is_401(guarded_client: tuple[FastAPI, TestClient]) -> None:
    _, client = guarded_client
    response = client.get("/guarded/one")
    assert response.status_code == 401
