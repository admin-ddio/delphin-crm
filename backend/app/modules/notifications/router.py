"""HTTP surface of the notifications module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "notifications", "description": "In-app notifications and preferences"}

router = APIRouter(prefix="/notifications", tags=["notifications"])
