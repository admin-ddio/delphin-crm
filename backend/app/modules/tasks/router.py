"""HTTP surface of the tasks module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "tasks", "description": "Tasks, versions and review"}

router = APIRouter(prefix="/tasks", tags=["tasks"])
