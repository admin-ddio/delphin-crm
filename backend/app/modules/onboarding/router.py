"""HTTP surface of the onboarding module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "onboarding", "description": "Client onboarding workflow and public questionnaire"}

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
