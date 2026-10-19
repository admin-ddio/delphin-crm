"""Project templates. From the clickable demo; TODO(pilot-port): the pilot's template table."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class TemplateTask:
    title: str
    start_offset_days: int
    duration_days: int
    requires_review: bool
    requires_client_approval: bool


@dataclass(frozen=True, slots=True)
class ProjectTemplate:
    key: str
    name: str
    tasks: tuple[TemplateTask, ...]


SEO_FOUNDATION: Final = ProjectTemplate(
    key="seo_foundation",
    name="SEO onboarding & foundation",
    tasks=(
        TemplateTask("Baseline SEO audit", 0, 5, True, False),
        TemplateTask("Keyword research", 0, 7, True, False),
        TemplateTask("Technical fixes roadmap", 5, 5, True, True),
        TemplateTask("On-page optimisation of priority pages", 12, 14, True, False),
        TemplateTask("Month 1 performance report", 25, 5, True, True),
    ),
)

TEMPLATES: Final = {SEO_FOUNDATION.key: SEO_FOUNDATION}
