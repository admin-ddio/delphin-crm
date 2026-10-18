"""HTTP surface of the finance module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "finance", "description": "Invoices, payments, expenses"}

router = APIRouter(prefix="/finance", tags=["finance"])
