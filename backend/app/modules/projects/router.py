"""HTTP surface of the projects module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "projects", "description": "Projects and boards"}

router = APIRouter(prefix="/projects", tags=["projects"])
