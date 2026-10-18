"""HTTP surface of the meetings module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "meetings", "description": "Meetings"}

router = APIRouter(prefix="/meetings", tags=["meetings"])
