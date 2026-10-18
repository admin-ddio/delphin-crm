"""HTTP surface of the settings module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {
    "name": "settings",
    "description": (
        "Administration: roles, onboarding config, automation, jobs, integrations, audit"
    ),
}

router = APIRouter(prefix="/settings", tags=["settings"])
