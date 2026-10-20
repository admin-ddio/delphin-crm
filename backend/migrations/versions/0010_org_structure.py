"""organization structure: typed reporting lines, department owners, role settings

Additive and data-preserving:
- reporting lines: direct → direct_manager, dotted → functional_manager; new kinds,
  optional project, ended_by; employees.leave_approver_id becomes leave_approver
  lines (then the column is dropped);
- departments: delivery manager, executive owners (department_owners); two renamed
  (Content Writers Team → Content Team, Development Team → Web Development Team) and
  three added, with purposes; existing rows are never deleted;
- designations: belong to a department (company-level titles have none); the
  brief's suggested titles are added; COO → Co-Founder & COO;
- employees: is_executive (set for the founder titles);
- roles: the org.* permissions are added to the existing roles (nothing removed),
  and the Organization Admin role is created with no members.

Revision ID: 0010_org_structure
Revises: 0009_onboarding_v2
Create Date: 2026-10-20 09:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_org_structure"
down_revision: str | None = "0009_onboarding_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "direct_manager",
    "functional_manager",
    "project_manager",
    "department_head",
    "leave_approver",
    "performance_reviewer",
    "executive_escalation",
)
RENAMES = (("Content Writers Team", "Content Team"), ("Development Team", "Web Development Team"))
DEPARTMENTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "Content Team": (
        "Content strategy, research, copywriting, and content production.",
        (
            "Head of Content / Content Lead",
            "Senior Content Writer",
            "Content Writer",
            "SEO Content Writer",
            "Copywriter",
            "Content Editor / Proofreader",
            "Content Strategist",
        ),
    ),
    "Design Team": (
        "Brand identity, creative design, social media creatives, digital advertisements, "
        "UI/UX, and visual communication.",
        (
            "Creative Director / Design Lead",
            "Senior Graphic Designer",
            "Graphic Designer",
            "Junior Graphic Designer",
            "UI/UX Designer",
            "Brand Designer",
            "Motion Graphics Designer",
            "Video Editor",
        ),
    ),
    "SEO Team": (
        "Technical SEO, on-page SEO, off-page SEO, keyword research, local SEO, audits, "
        "and organic growth reporting.",
        (
            "SEO Director / SEO Lead",
            "SEO Manager",
            "Senior SEO Specialist",
            "SEO Executive",
            "Technical SEO Specialist",
            "Local SEO / Google Business Profile Specialist",
            "Link Building Specialist",
            "SEO Analyst",
        ),
    ),
    "Social Media Team": (
        "Social strategy, content calendars, community management, publishing, reporting, "
        "and social media growth.",
        (
            "Social Media Lead",
            "Social Media Manager",
            "Social Media Executive",
            "Social Media Strategist",
            "Community Manager",
            "Short-Form Video / Reels Specialist",
        ),
    ),
    "Performance Marketing Team": (
        "Paid media strategy, campaign execution, optimization, tracking, and performance "
        "reporting.",
        (
            "Performance Marketing Lead",
            "Performance Marketing Manager",
            "Google Ads Specialist",
            "Meta Ads Specialist",
            "Paid Media Executive",
            "Conversion Rate Optimization Specialist",
            "Marketing Analytics / Tracking Specialist",
        ),
    ),
    "Web Development Team": (
        "Website development, CMS implementation, WordPress, frontend/backend development, "
        "maintenance, and technical support.",
        (
            "Web Development Lead",
            "Technical Lead",
            "Senior Full-Stack Developer",
            "Frontend Developer",
            "Backend Developer",
            "WordPress Developer",
            "Web Developer",
            "QA Tester",
        ),
    ),
    "Application Development Team": (
        "Web applications, mobile applications, APIs, integrations, databases, testing, "
        "deployment, and maintenance.",
        (
            "Application Development Lead",
            "Software Architect",
            "Technical Lead",
            "Senior Software Engineer",
            "Full-Stack Developer",
            "Mobile Application Developer",
            "Backend/API Developer",
            "QA / Automation Engineer",
            "DevOps Engineer",
        ),
    ),
    "Project Management Team": (
        "Project planning, task assignment, client coordination, timelines, resource "
        "allocation, and delivery quality.",
        (
            "Project Management Lead",
            "Project Manager",
            "Associate Project Manager",
            "Project Coordinator",
            "Delivery Coordinator",
        ),
    ),
    "Operations Team": (
        "Internal operations, process management, HR coordination, resource planning, "
        "administration, and workflow compliance.",
        (
            "Head of Operations",
            "Operations Manager",
            "HR / Operations Executive",
            "HR Coordinator",
            "Administration Executive",
            "Resource Coordinator",
        ),
    ),
}
FOUNDER_TITLES = ("Founder & CEO", "Co-Founder & COO", "Co-Founder")

EVERYONE = ["org.view", "org.directory.view"]
ROLE_GRANTS: dict[str, list[str]] = {
    "admin": EVERYONE,
    "account_manager": [*EVERYONE, "org.team.view"],
    "project_manager": [*EVERYONE, "org.team.view", "org.projects.assign"],
    "team_lead": [*EVERYONE, "org.team.view"],
    "employee": EVERYONE,
    "finance": EVERYONE,
    "hr_admin": [*EVERYONE, "org.team.view"],
}
ORG_ADMIN_PERMISSIONS = [
    "org.view",
    "org.directory.view",
    "org.team.view",
    "org.departments.manage",
    "org.designations.manage",
    "org.reporting.manage",
    "org.projects.assign",
    "org.roles.manage",
    "org.roles.assign",
    "org.audit.view",
]


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    conn = op.get_bind()

    # ---------------------------------------------------------------- departments
    op.add_column("departments", sa.Column("delivery_manager_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_departments_delivery_manager_id_employees"),
        "departments",
        "employees",
        ["delivery_manager_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "department_owners",
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["department_id"],
            ["departments.id"],
            name=op.f("fk_department_owners_department_id_departments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_department_owners_employee_id_employees"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_department_owners_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("department_id", "employee_id", name=op.f("pk_department_owners")),
    )

    # ---------------------------------------------------------------- designations
    op.add_column("designations", sa.Column("department_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_designations_department_id_departments"),
        "designations",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint(op.f("uq_designations_name"), "designations", type_="unique")
    op.create_index(
        "uq_designations_department_id_name",
        "designations",
        ["department_id", "name"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )

    # ---------------------------------------------------------------- employees
    op.add_column(
        "employees",
        sa.Column("is_executive", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    # ---------------------------------------------------------------- reporting lines
    op.drop_index(
        "uq_reporting_lines_direct_open",
        table_name="reporting_lines",
        postgresql_where=sa.text("kind = 'direct' AND ends_on IS NULL"),
    )
    op.drop_constraint(op.f("ck_reporting_lines_kind"), "reporting_lines", type_="check")
    op.alter_column("reporting_lines", "kind", type_=sa.String(length=30), existing_nullable=False)
    op.execute("UPDATE reporting_lines SET kind = 'direct_manager' WHERE kind = 'direct'")
    op.execute("UPDATE reporting_lines SET kind = 'functional_manager' WHERE kind = 'dotted'")
    op.add_column("reporting_lines", sa.Column("project_id", sa.UUID(), nullable=True))
    op.add_column("reporting_lines", sa.Column("ended_by_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_reporting_lines_project_id_projects"),
        "reporting_lines",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_reporting_lines_ended_by_id_users"),
        "reporting_lines",
        "users",
        ["ended_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_reporting_lines_kind"), "reporting_lines", _in("kind", KINDS)
    )
    op.create_check_constraint(
        op.f("ck_reporting_lines_period"),
        "reporting_lines",
        "ends_on IS NULL OR ends_on >= starts_on",
    )
    op.create_check_constraint(
        op.f("ck_reporting_lines_project_kind"),
        "reporting_lines",
        "project_id IS NULL OR kind = 'project_manager'",
    )
    # Explicit leave approvers become leave_approver lines (history starts today).
    op.execute(
        "INSERT INTO reporting_lines (employee_id, manager_id, kind, starts_on, created_at) "
        "SELECT id, leave_approver_id, 'leave_approver', current_date, now() "
        "FROM employees WHERE leave_approver_id IS NOT NULL"
    )
    op.drop_constraint(op.f("ck_employees_approver"), "employees", type_="check")
    op.drop_constraint(
        op.f("fk_employees_leave_approver_id_employees"), "employees", type_="foreignkey"
    )
    op.drop_column("employees", "leave_approver_id")
    op.create_index(
        "uq_reporting_lines_single_open",
        "reporting_lines",
        ["employee_id", "kind"],
        unique=True,
        postgresql_where=sa.text(
            "ends_on IS NULL AND kind NOT IN ('functional_manager', 'project_manager')"
        ),
    )
    op.create_index(
        "uq_reporting_lines_multi_open",
        "reporting_lines",
        ["employee_id", "kind", "manager_id", "project_id"],
        unique=True,
        postgresql_where=sa.text("ends_on IS NULL"),
        postgresql_nulls_not_distinct=True,
    )
    op.create_index("ix_reporting_lines_project_id", "reporting_lines", ["project_id"])

    # ---------------------------------------------------------------- default configuration
    for old, new in RENAMES:
        # Skip when an admin already created the new name.
        conn.execute(
            sa.text(
                "UPDATE departments SET name = :new WHERE name = :old "
                "AND NOT EXISTS (SELECT 1 FROM departments WHERE name = :new)"
            ),
            {"old": old, "new": new},
        )
    for name, (purpose, titles) in DEPARTMENTS.items():
        conn.execute(
            sa.text(
                "INSERT INTO departments (name, description) VALUES (:name, :purpose) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {"name": name, "purpose": purpose},
        )
        conn.execute(
            sa.text(
                "UPDATE departments SET description = :purpose "
                "WHERE name = :name AND description IS NULL"
            ),
            {"name": name, "purpose": purpose},
        )
        department_id = conn.execute(
            sa.text("SELECT id FROM departments WHERE name = :name"), {"name": name}
        ).scalar_one()
        for title in titles:
            # A matching company-level title (e.g. "Project Manager") moves into the department.
            moved = conn.execute(
                sa.text(
                    "UPDATE designations SET department_id = :d "
                    "WHERE name = :t AND department_id IS NULL RETURNING id"
                ),
                {"d": department_id, "t": title},
            ).first()
            if moved is None:
                conn.execute(
                    sa.text(
                        "INSERT INTO designations (name, department_id) VALUES (:t, :d) "
                        "ON CONFLICT DO NOTHING"
                    ),
                    {"d": department_id, "t": title},
                )
    conn.execute(
        sa.text(
            "UPDATE designations SET name = 'Co-Founder & COO' WHERE name = 'COO' "
            "AND department_id IS NULL AND NOT EXISTS "
            "(SELECT 1 FROM designations WHERE name = 'Co-Founder & COO')"
        )
    )
    for title in FOUNDER_TITLES:
        conn.execute(
            sa.text("INSERT INTO designations (name) VALUES (:t) ON CONFLICT DO NOTHING"),
            {"t": title},
        )
    conn.execute(
        sa.text(
            "UPDATE employees SET is_executive = true WHERE designation_id IN "
            "(SELECT id FROM designations WHERE department_id IS NULL AND name IN :titles)"
        ).bindparams(sa.bindparam("titles", expanding=True)),
        {"titles": list(FOUNDER_TITLES)},
    )

    # ---------------------------------------------------------------- roles
    for key, grants in ROLE_GRANTS.items():
        conn.execute(
            sa.text(
                "UPDATE roles SET permissions = ARRAY("
                "SELECT DISTINCT p FROM unnest(permissions || CAST(:grants AS varchar[])) AS p "
                "ORDER BY p) WHERE key = :key"
            ),
            {"key": key, "grants": grants},
        )
    conn.execute(
        sa.text(
            "INSERT INTO roles (key, name, description, permissions, is_system) "
            "VALUES ('org_admin', 'Organization Admin', "
            "'Departments, designations, reporting lines and role definitions only.', "
            "CAST(:perms AS varchar[]), true) ON CONFLICT (key) DO NOTHING"
        ),
        {"perms": ORG_ADMIN_PERMISSIONS},
    )


def downgrade() -> None:
    """Best effort: new relationship kinds, department owners and the org.* grants are
    dropped; open leave-approver lines go back to the employee column."""
    conn = op.get_bind()

    conn.execute(sa.text("DELETE FROM roles WHERE key = 'org_admin'"))
    conn.execute(
        sa.text(
            "UPDATE roles SET permissions = ARRAY("
            "SELECT p FROM unnest(permissions) AS p WHERE p NOT LIKE 'org.%' ORDER BY p)"
        )
    )

    op.add_column("employees", sa.Column("leave_approver_id", sa.UUID(), nullable=True))
    op.execute(
        "UPDATE employees e SET leave_approver_id = r.manager_id FROM reporting_lines r "
        "WHERE r.employee_id = e.id AND r.kind = 'leave_approver' AND r.ends_on IS NULL"
    )
    op.create_foreign_key(
        op.f("fk_employees_leave_approver_id_employees"),
        "employees",
        "employees",
        ["leave_approver_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        op.f("ck_employees_approver"),
        "employees",
        "leave_approver_id IS NULL OR leave_approver_id <> id",
    )

    op.drop_index("ix_reporting_lines_project_id", table_name="reporting_lines")
    op.drop_index(
        "uq_reporting_lines_multi_open",
        table_name="reporting_lines",
        postgresql_where=sa.text("ends_on IS NULL"),
    )
    op.drop_index(
        "uq_reporting_lines_single_open",
        table_name="reporting_lines",
        postgresql_where=sa.text(
            "ends_on IS NULL AND kind NOT IN ('functional_manager', 'project_manager')"
        ),
    )
    op.drop_constraint(op.f("ck_reporting_lines_project_kind"), "reporting_lines", type_="check")
    op.drop_constraint(op.f("ck_reporting_lines_period"), "reporting_lines", type_="check")
    op.drop_constraint(op.f("ck_reporting_lines_kind"), "reporting_lines", type_="check")
    op.execute(
        "DELETE FROM reporting_lines WHERE kind NOT IN ('direct_manager', 'functional_manager')"
    )
    # The old schema allowed one open dotted line per manager without a project.
    op.execute("UPDATE reporting_lines SET kind = 'direct' WHERE kind = 'direct_manager'")
    op.execute("UPDATE reporting_lines SET kind = 'dotted' WHERE kind = 'functional_manager'")
    op.drop_constraint(
        op.f("fk_reporting_lines_ended_by_id_users"), "reporting_lines", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_reporting_lines_project_id_projects"), "reporting_lines", type_="foreignkey"
    )
    op.drop_column("reporting_lines", "ended_by_id")
    op.drop_column("reporting_lines", "project_id")
    op.alter_column("reporting_lines", "kind", type_=sa.String(length=10), existing_nullable=False)
    op.create_check_constraint(
        op.f("ck_reporting_lines_kind"), "reporting_lines", "kind IN ('direct', 'dotted')"
    )
    op.create_index(
        "uq_reporting_lines_direct_open",
        "reporting_lines",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'direct' AND ends_on IS NULL"),
    )

    op.drop_column("employees", "is_executive")

    # Titles that now exist in two departments collapse to one (employees follow it).
    op.execute(
        "UPDATE employees e SET designation_id = keep.id FROM designations d, "
        "(SELECT DISTINCT ON (name) id, name FROM designations ORDER BY name, created_at, id) keep "
        "WHERE e.designation_id = d.id AND d.name = keep.name AND d.id <> keep.id"
    )
    op.execute(
        "DELETE FROM designations d USING designations k "
        "WHERE d.name = k.name AND (d.created_at, d.id) > (k.created_at, k.id)"
    )
    op.execute("UPDATE designations SET name = 'COO' WHERE name = 'Co-Founder & COO'")
    op.drop_index(
        "uq_designations_department_id_name",
        table_name="designations",
        postgresql_nulls_not_distinct=True,
    )
    op.create_unique_constraint(op.f("uq_designations_name"), "designations", ["name"])
    op.drop_constraint(
        op.f("fk_designations_department_id_departments"), "designations", type_="foreignkey"
    )
    op.drop_column("designations", "department_id")

    op.drop_table("department_owners")
    op.drop_constraint(
        op.f("fk_departments_delivery_manager_id_employees"), "departments", type_="foreignkey"
    )
    op.drop_column("departments", "delivery_manager_id")
    for old, new in RENAMES:
        conn.execute(
            sa.text(
                "UPDATE departments SET name = :old WHERE name = :new "
                "AND NOT EXISTS (SELECT 1 FROM departments WHERE name = :old)"
            ),
            {"old": old, "new": new},
        )
