"""HTTP surface of the services module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "services", "description": "Services, retainers, templates and workspaces"}

router = APIRouter(prefix="/services", tags=["services"])
