"""Mounts /api/v1 and every module router. Add new modules here and in MODULE_SLOTS."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.modules.activity import router as activity
from app.modules.approvals import router as approvals
from app.modules.auth import router as auth
from app.modules.clients import router as clients
from app.modules.content import router as content
from app.modules.dashboard import router as dashboard
from app.modules.documents import router as documents
from app.modules.finance import router as finance
from app.modules.jobs import router as jobs
from app.modules.meetings import router as meetings
from app.modules.notifications import router as notifications
from app.modules.onboarding import router as onboarding
from app.modules.projects import router as projects
from app.modules.reports import router as reports
from app.modules.search import router as search
from app.modules.seo import router as seo
from app.modules.services import router as services
from app.modules.settings import router as settings
from app.modules.tasks import router as tasks
from app.modules.team import router as team

API_PREFIX = "/api/v1"

# Canonical slot order (matches docs/pilot-parity.md and frontend/src/features/).
MODULE_SLOTS = (
    auth,
    dashboard,
    notifications,
    clients,
    onboarding,
    projects,
    tasks,
    approvals,
    meetings,
    services,
    seo,
    content,
    team,
    documents,
    reports,
    finance,
    search,
    settings,
    activity,
    jobs,
)

OPENAPI_TAGS: list[dict[str, Any]] = [
    {"name": "health", "description": "Liveness and readiness probes"},
    *(dict(module.TAG) for module in MODULE_SLOTS),
]

api_router = APIRouter(prefix=API_PREFIX)
for module in MODULE_SLOTS:
    api_router.include_router(module.router)
api_router.include_router(documents.files_router)
