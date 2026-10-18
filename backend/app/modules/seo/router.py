"""HTTP surface of the seo module. No endpoints until the feature is ported."""

from __future__ import annotations

from fastapi import APIRouter

TAG = {"name": "seo", "description": "SEO"}

router = APIRouter(prefix="/seo", tags=["seo"])
