"""HTTP surface of the approvals module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "approvals", "description": "Internal and client approvals"}

router = APIRouter(prefix="/approvals", tags=["approvals"])
