"""HTTP surface of the clients module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "clients", "description": "CRM & Clients"}

router = APIRouter(prefix="/clients", tags=["clients"])
