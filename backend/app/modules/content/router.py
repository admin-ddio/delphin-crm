"""HTTP surface of the content module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "content", "description": "Content & Social"}

router = APIRouter(prefix="/content", tags=["content"])
