"""services and retainers: catalogue, editable templates, client services

Additive: four new tables, the five services Delphin sells (retainers: SEO, Social
Media; projects: SEO-friendly Website, Web Application, Mobile Application) with
their default task templates, and three permissions granted to existing roles
(nothing removed). Existing clients and projects are untouched.

Revision ID: 0011_services
Revises: 0010_org_structure
Create Date: 2026-10-27 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_services"
down_revision: str | None = "0010_org_structure"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (key, name, kind, department, sort)
SERVICE_TYPES = (
    ("seo", "SEO", "retainer", "SEO Team", 1),
    ("social_media", "Social Media Marketing", "retainer", "Social Media Team", 2),
    ("website", "SEO-friendly Website", "project", "Web Development Team", 3),
    ("web_app", "Web Application", "project", "Application Development Team", 4),
    ("mobile_app", "Mobile Application", "project", "Application Development Team", 5),
)

# Monthly: (title, day_of_month, review, client_approval, area)
# Setup / delivery: (title, start_offset_days, duration_days, review, client_approval, area)
MONTHLY = {
    "seo": (
        ("Keyword tracking update", 4, False, False, "seo"),
        ("Monthly performance report", 6, True, True, "seo"),
        ("Monthly SEO audit", 11, True, False, "seo"),
        ("On-page optimisation batch", 15, True, False, "seo"),
        ("Link building & outreach", 20, False, False, "seo"),
        ("Next month content / blog plan", 25, True, True, "content"),
    ),
    "social_media": (
        ("Scheduling & publishing", 1, False, False, "social"),
        ("Monthly social report", 5, True, True, "social"),
        ("Community management check-in", 15, False, False, "social"),
        ("Next month content calendar", 20, True, True, "social"),
        ("Creatives & captions batch", 25, True, True, "design"),
    ),
}
SETUP = {
    "seo": (
        ("Baseline SEO audit", 0, 5, True, False, "seo"),
        ("Keyword research", 0, 7, True, False, "seo"),
        ("Technical fixes roadmap", 5, 5, True, True, "seo"),
        ("On-page optimisation of priority pages", 12, 14, True, False, "seo"),
        ("Month 1 performance report", 25, 5, True, True, "seo"),
    ),
    "social_media": (
        ("Social audit & competitor review", 0, 5, True, False, "social"),
        ("Brand voice & content pillars", 5, 5, True, True, "social"),
        ("Profile optimisation", 5, 5, True, False, "social"),
        ("Posting schedule setup", 10, 3, True, False, "social"),
    ),
}
DELIVERY = {
    "website": (
        ("Discovery & requirements", 0, 5, True, True, "project_management"),
        ("Sitemap & content plan", 5, 5, True, True, "content"),
        ("UI design", 10, 10, True, True, "design"),
        ("Development", 20, 20, True, False, "development"),
        ("On-page SEO setup", 40, 4, True, False, "seo"),
        ("Content upload", 40, 5, True, False, "content"),
        ("QA & testing", 45, 5, True, False, "development"),
        ("Launch & handover", 50, 2, True, True, "development"),
    ),
    "web_app": (
        ("Discovery & requirements", 0, 7, True, True, "project_management"),
        ("Architecture & technical plan", 7, 5, True, False, "development"),
        ("UI/UX design", 7, 14, True, True, "design"),
        ("Sprint 1", 21, 14, True, False, "development"),
        ("Sprint 2", 35, 14, True, False, "development"),
        ("QA & UAT", 49, 7, True, True, "development"),
        ("Deployment & launch", 56, 3, True, True, "development"),
        ("Handover & documentation", 59, 3, True, False, "development"),
    ),
    "mobile_app": (
        ("Discovery & requirements", 0, 7, True, True, "project_management"),
        ("UI/UX design", 7, 14, True, True, "design"),
        ("Build 1", 21, 21, True, False, "development"),
        ("Build 2", 42, 14, True, False, "development"),
        ("QA on devices", 56, 7, True, False, "development"),
        ("Store listing & submission", 63, 5, True, True, "development"),
        ("Launch & handover", 68, 3, True, True, "development"),
    ),
}

ROLE_GRANTS: dict[str, list[str]] = {
    "account_manager": ["services.view_all"],
    "project_manager": ["services.view_all", "services.templates.manage"],
    "finance": ["services.view_all"],
}
NEW_PERMISSIONS = ("services.view_all", "services.templates.manage", "users.manage")


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _id() -> sa.Column[object]:
    return sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "service_types",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=True),
        sa.Column("sort", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _id(),
        *_timestamps(),
        sa.CheckConstraint("kind IN ('retainer', 'project')", name=op.f("ck_service_types_kind")),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name=op.f("fk_service_types_department_id_departments"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_types")),
        sa.UniqueConstraint("key", name=op.f("uq_service_types_key")),
    )
    op.create_table(
        "service_template_tasks",
        sa.Column("service_type_id", sa.UUID(), nullable=False),
        sa.Column("phase", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("day_of_month", sa.Integer(), nullable=True),
        sa.Column("start_offset_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("requires_review", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "requires_client_approval",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("area", sa.String(length=30), nullable=True),
        sa.Column("sort", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _id(),
        *_timestamps(),
        sa.CheckConstraint(
            "phase IN ('setup', 'monthly', 'delivery')",
            name=op.f("ck_service_template_tasks_phase"),
        ),
        sa.CheckConstraint(
            "(phase = 'monthly') = (day_of_month IS NOT NULL)",
            name=op.f("ck_service_template_tasks_monthly_day"),
        ),
        sa.CheckConstraint(
            "day_of_month IS NULL OR day_of_month BETWEEN 1 AND 28",
            name=op.f("ck_service_template_tasks_day"),
        ),
        sa.CheckConstraint(
            "start_offset_days >= 0 AND duration_days >= 0",
            name=op.f("ck_service_template_tasks_offsets"),
        ),
        sa.ForeignKeyConstraint(
            ["service_type_id"],
            ["service_types.id"],
            name=op.f("fk_service_template_tasks_service_type_id_service_types"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_template_tasks")),
    )
    op.create_index(
        "ix_service_template_tasks_service_type_id",
        "service_template_tasks",
        ["service_type_id", "phase", "sort"],
    )
    op.create_table(
        "client_services",
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("service_type_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column(
            "status", sa.String(length=10), server_default=sa.text("'planned'"), nullable=False
        ),
        sa.Column("fee", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'INR'"), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("manager_id", sa.UUID(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        _id(),
        *_timestamps(),
        sa.CheckConstraint("kind IN ('retainer', 'project')", name=op.f("ck_client_services_kind")),
        sa.CheckConstraint(
            "status IN ('planned', 'active', 'paused', 'completed', 'cancelled')",
            name=op.f("ck_client_services_status"),
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name=op.f("ck_client_services_period"),
        ),
        sa.CheckConstraint("fee IS NULL OR fee >= 0", name=op.f("ck_client_services_fee")),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
            name=op.f("fk_client_services_client_id_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_type_id"],
            ["service_types.id"],
            name=op.f("fk_client_services_service_type_id_service_types"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_client_services_project_id_projects"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["manager_id"],
            ["users.id"],
            name=op.f("fk_client_services_manager_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_client_services_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_services")),
        sa.UniqueConstraint("code", name=op.f("uq_client_services_code")),
        sa.UniqueConstraint("project_id", name=op.f("uq_client_services_project_id")),
    )
    op.create_index(
        "uq_client_services_open_retainer",
        "client_services",
        ["client_id", "service_type_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'retainer' AND status IN ('planned', 'active', 'paused')"),
    )
    op.create_index("ix_client_services_client_id", "client_services", ["client_id"])
    op.create_index("ix_client_services_status", "client_services", ["status"])
    op.create_table(
        "service_occurrences",
        sa.Column("client_service_id", sa.UUID(), nullable=False),
        sa.Column("template_task_id", sa.UUID(), nullable=False),
        sa.Column("occurrence_key", sa.String(length=7), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _id(),
        sa.ForeignKeyConstraint(
            ["client_service_id"],
            ["client_services.id"],
            name=op.f("fk_service_occurrences_client_service_id_client_services"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["template_task_id"],
            ["service_template_tasks.id"],
            name=op.f("fk_service_occurrences_template_task_id_service_template_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_service_occurrences_task_id_tasks"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_occurrences")),
        sa.UniqueConstraint(
            "client_service_id",
            "template_task_id",
            "occurrence_key",
            name="uq_service_occurrences_period",
        ),
    )

    # ---------------------------------------------------------------- catalogue
    conn = op.get_bind()
    for key, name, kind, department, sort in SERVICE_TYPES:
        type_id = conn.execute(
            sa.text(
                "INSERT INTO service_types (key, name, kind, department_id, sort) "
                "VALUES (:key, :name, :kind, "
                "(SELECT id FROM departments WHERE name = :department), :sort) RETURNING id"
            ),
            {"key": key, "name": name, "kind": kind, "department": department, "sort": sort},
        ).scalar_one()
        rows: list[dict[str, object]] = []
        for i, (title, day, review, approval, area) in enumerate(MONTHLY.get(key, ())):
            rows.append(
                {
                    "phase": "monthly",
                    "title": title,
                    "day": day,
                    "offset": 0,
                    "duration": 0,
                    "review": review,
                    "approval": approval,
                    "area": area,
                    "sort": i,
                }
            )
        for phase, table in (("setup", SETUP), ("delivery", DELIVERY)):
            for i, (title, offset, duration, review, approval, area) in enumerate(
                table.get(key, ())
            ):
                rows.append(
                    {
                        "phase": phase,
                        "title": title,
                        "day": None,
                        "offset": offset,
                        "duration": duration,
                        "review": review,
                        "approval": approval,
                        "area": area,
                        "sort": i,
                    }
                )
        for row in rows:
            conn.execute(
                sa.text(
                    "INSERT INTO service_template_tasks (service_type_id, phase, title, "
                    "day_of_month, start_offset_days, duration_days, requires_review, "
                    "requires_client_approval, area, sort) VALUES (:type_id, :phase, :title, "
                    ":day, :offset, :duration, :review, :approval, :area, :sort)"
                ),
                {"type_id": type_id, **row},
            )

    # ---------------------------------------------------------------- permissions
    for key, grants in ROLE_GRANTS.items():
        conn.execute(
            sa.text(
                "UPDATE roles SET permissions = ARRAY("
                "SELECT DISTINCT p FROM unnest(permissions || CAST(:grants AS varchar[])) AS p "
                "ORDER BY p) WHERE key = :key"
            ),
            {"key": key, "grants": grants},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE roles SET permissions = ARRAY("
            "SELECT p FROM unnest(permissions) AS p WHERE NOT (p = ANY(CAST(:gone AS varchar[]))) "
            "ORDER BY p)"
        ),
        {"gone": list(NEW_PERMISSIONS)},
    )
    op.drop_table("service_occurrences")
    op.drop_index("ix_client_services_status", table_name="client_services")
    op.drop_index("ix_client_services_client_id", table_name="client_services")
    op.drop_index(
        "uq_client_services_open_retainer",
        table_name="client_services",
        postgresql_where=sa.text("kind = 'retainer' AND status IN ('planned', 'active', 'paused')"),
    )
    op.drop_table("client_services")
    op.drop_index("ix_service_template_tasks_service_type_id", table_name="service_template_tasks")
    op.drop_table("service_template_tasks")
    op.drop_table("service_types")
