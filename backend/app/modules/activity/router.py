"""HTTP surface of the activity module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "activity", "description": "Organisation-wide activity log"}

router = APIRouter(prefix="/activity", tags=["activity"])
