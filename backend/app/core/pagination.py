"""Pagination envelope and validated sorting.

List endpoints return Page[T] = {items, total, page, page_size}.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import Annotated, Generic, Literal, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field

from app.core.errors import ValidationFailed

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200

SortDirection = Literal["asc", "desc"]


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


def page_params(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> PageParams:
    """FastAPI dependency for ?page=&page_size=."""
    return PageParams(page=page, page_size=page_size)


T = TypeVar("T")


class Page(BaseModel, Generic[T]):  # noqa: UP046  # explicit Generic is the form pydantic documents
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)

    @classmethod
    def create(cls, items: Sequence[T], total: int, params: PageParams) -> Page[T]:
        return cls(items=list(items), total=total, page=params.page, page_size=params.page_size)


def parse_sort(value: str | None, allowed: Collection[str]) -> list[tuple[str, SortDirection]]:
    """Parse "?sort=name,-created_at" against an allow-list of field names."""
    if not value:
        return []
    result: list[tuple[str, SortDirection]] = []
    for raw in value.split(","):
        token = raw.strip()
        if not token:
            continue
        direction: SortDirection = "desc" if token.startswith("-") else "asc"
        field = token.lstrip("-+")
        if field not in allowed:
            raise ValidationFailed(
                f"Cannot sort by '{field}'.", details={"sort": field, "allowed": sorted(allowed)}
            )
        result.append((field, direction))
    return result
