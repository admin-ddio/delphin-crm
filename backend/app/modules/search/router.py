"""HTTP surface of the search module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "search", "description": "Global search"}

router = APIRouter(prefix="/search", tags=["search"])
