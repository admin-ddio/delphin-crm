"""platform core: identity, audit (append-only), activity, notifications, system, jobs

Revision ID: 0001_platform_core
Revises:
Create Date: 2026-10-16

Business tables are NOT here; each is ported with its feature (docs/pilot-parity.md).

Downgrade note: downgrading drops audit_log and with it the audit history. That is
refused when APP_ENV=production unless ALLOW_AUDIT_LOG_DOWNGRADE=true is set
explicitly. Extensions are left installed on downgrade (they may be shared).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001_platform_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXTENSIONS = ("pgcrypto", "citext", "pg_trgm")

# TODO(pilot-port): diff against the pilot's AuditLog trigger migration and align
# function/trigger names and the error message if the pilot's are referenced anywhere.
AUDIT_GUARD_FUNCTION = """
CREATE OR REPLACE FUNCTION audit_log_reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only: % is not allowed', TG_OP
    USING ERRCODE = 'insufficient_privilege';
END;
$$;
"""
AUDIT_GUARD_TRIGGERS = (
    "CREATE TRIGGER audit_log_no_update_delete BEFORE UPDATE OR DELETE ON audit_log "
    "FOR EACH ROW EXECUTE FUNCTION audit_log_reject_mutation();",
    "CREATE TRIGGER audit_log_no_truncate BEFORE TRUNCATE ON audit_log "
    "FOR EACH STATEMENT EXECUTE FUNCTION audit_log_reject_mutation();",
)


def _uuid_pk() -> sa.Column[Any]:
    return sa.Column(
        "id", pg.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False
    )


def _ts(name: str, *, nullable: bool = False, default_now: bool = True) -> sa.Column[Any]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.func.now() if default_now else None,
        nullable=nullable,
    )


def _jsonb(name: str, default: str = "'{}'::jsonb") -> sa.Column[Any]:
    return sa.Column(name, pg.JSONB(), server_default=sa.text(default), nullable=False)


def upgrade() -> None:
    for extension in EXTENSIONS:
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension}")

    # ------------------------------------------------------------- identity
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("email", pg.CITEXT(), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.false(), nullable=False),
        _ts("activated_at", nullable=True, default_now=False),
        _ts("last_login_at", nullable=True, default_now=False),
        sa.Column("failed_login_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        _ts("locked_until", nullable=True, default_now=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "roles",
        _uuid_pk(),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "permissions",
            pg.ARRAY(sa.String(100)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
        sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("key", name=op.f("uq_roles_key")),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", pg.UUID(as_uuid=True), nullable=False),
        _ts("assigned_at"),
        sa.Column("assigned_by_id", pg.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name=op.f("fk_user_roles_role_id_roles"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_id"],
            ["users.id"],
            name=op.f("fk_user_roles_assigned_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name=op.f("pk_user_roles")),
    )
    op.create_index(op.f("ix_user_roles_role_id"), "user_roles", ["role_id"])

    op.create_table(
        "sessions",
        _uuid_pk(),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        _ts("created_at"),
        _ts("last_seen_at"),
        _ts("expires_at", default_now=False),
        _ts("revoked_at", nullable=True, default_now=False),
        sa.Column("ip", pg.INET(), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"])
    op.create_index(op.f("ix_sessions_expires_at"), "sessions", ["expires_at"])

    op.create_table(
        "auth_tokens",
        _uuid_pk(),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        _ts("expires_at", default_now=False),
        _ts("used_at", nullable=True, default_now=False),
        _ts("created_at"),
        sa.Column("created_by_id", pg.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('invite', 'password_reset')", name=op.f("ck_auth_tokens_purpose")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_auth_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_auth_tokens_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_tokens_token_hash")),
    )
    op.create_index(op.f("ix_auth_tokens_user_id"), "auth_tokens", ["user_id"])

    # ------------------------------------------------------------- audit (append-only)
    op.create_table(
        "audit_log",
        _uuid_pk(),
        _ts("occurred_at"),
        sa.Column("actor_user_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("ip", pg.INET(), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        _jsonb("changes"),
        _jsonb("context"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index("ix_audit_log_entity_type_entity_id", "audit_log", ["entity_type", "entity_id"])
    op.create_index("ix_audit_log_actor_user_id", "audit_log", ["actor_user_id"])
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])
    op.execute(AUDIT_GUARD_FUNCTION)
    for statement in AUDIT_GUARD_TRIGGERS:
        op.execute(statement)

    # ------------------------------------------------------------- activity
    op.create_table(
        "activity_events",
        _uuid_pk(),
        _ts("occurred_at"),
        sa.Column("actor_user_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("verb", sa.String(100), nullable=False),
        sa.Column("subject_type", sa.String(100), nullable=False),
        sa.Column("subject_id", sa.String(100), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        _jsonb("context"),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_activity_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_events")),
    )
    op.create_index(
        "ix_activity_events_subject_type_subject_id",
        "activity_events",
        ["subject_type", "subject_id"],
    )
    op.create_index("ix_activity_events_occurred_at", "activity_events", ["occurred_at"])

    # ------------------------------------------------------------- notifications
    op.create_table(
        "notifications",
        _uuid_pk(),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.String(100), nullable=True),
        _ts("read_at", nullable=True, default_now=False),
        _ts("created_at"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index("ix_notifications_user_id_read_at", "notifications", ["user_id", "read_at"])

    op.create_table(
        "notification_preferences",
        _uuid_pk(),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        _ts("updated_at"),
        sa.CheckConstraint(
            "channel IN ('in_app', 'email')", name=op.f("ck_notification_preferences_channel")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notification_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_preferences")),
        sa.UniqueConstraint(
            "user_id",
            "kind",
            "channel",
            name=op.f("uq_notification_preferences_user_id_kind_channel"),
        ),
    )

    # ------------------------------------------------------------- system
    op.create_table(
        "settings",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", pg.JSONB(), nullable=False),
        _ts("updated_at"),
        sa.Column("updated_by_id", pg.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_settings_updated_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_settings")),
    )

    op.create_table(
        "counters",
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_counters")),
    )

    op.create_table(
        "saved_views",
        _uuid_pk(),
        sa.Column("owner_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("resource", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        _jsonb("filters"),
        _jsonb("sort", "'[]'::jsonb"),
        sa.Column("is_shared", sa.Boolean(), server_default=sa.false(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_saved_views_owner_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_saved_views")),
        sa.UniqueConstraint(
            "owner_id", "resource", "name", name=op.f("uq_saved_views_owner_id_resource_name")
        ),
    )

    op.create_table(
        "integration_configs",
        _uuid_pk(),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        _jsonb("config"),
        sa.Column("encrypted_secrets", sa.LargeBinary(), nullable=True),
        _ts("last_verified_at", nullable=True, default_now=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_configs")),
        sa.UniqueConstraint("provider", name=op.f("uq_integration_configs_provider")),
    )

    # ------------------------------------------------------------- jobs
    op.create_table(
        "job_runs",
        _uuid_pk(),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("triggered_by", sa.String(20), nullable=False),
        _ts("started_at"),
        _ts("finished_at", nullable=True, default_now=False),
        _jsonb("result"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed', 'skipped')",
            name=op.f("ck_job_runs_status"),
        ),
        sa.CheckConstraint(
            "triggered_by IN ('cron', 'manual', 'system')", name=op.f("ck_job_runs_triggered_by")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_runs")),
    )
    op.create_index("ix_job_runs_job_name_started_at", "job_runs", ["job_name", "started_at"])


def downgrade() -> None:
    if (
        os.environ.get("APP_ENV") == "production"
        and os.environ.get("ALLOW_AUDIT_LOG_DOWNGRADE") != "true"
    ):
        msg = (
            "Refusing to drop audit_log in production. "
            "Set ALLOW_AUDIT_LOG_DOWNGRADE=true to confirm destroying audit history."
        )
        raise RuntimeError(msg)

    op.drop_table("job_runs")
    op.drop_table("integration_configs")
    op.drop_table("saved_views")
    op.drop_table("counters")
    op.drop_table("settings")
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
    op.drop_table("activity_events")
    # Dropping the table drops its triggers; then the function.
    op.drop_table("audit_log")
    op.execute("DROP FUNCTION IF EXISTS audit_log_reject_mutation()")
    op.drop_table("auth_tokens")
    op.drop_table("sessions")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
