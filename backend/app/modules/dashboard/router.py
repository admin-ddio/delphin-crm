"""HTTP surface of the dashboard module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "dashboard", "description": "Organisation dashboard"}

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
