"""initial schema: users, repositories, scans, vulnerabilities

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-03
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# String-backed enums (native_enum=False -> stored as VARCHAR, no PG TYPE).
subscription_tier = sa.Enum(
    "free", "starter", "pro", "enterprise",
    name="subscription_tier", native_enum=False,
)
scan_status = sa.Enum(
    "pending", "running", "completed", "failed",
    name="scan_status", native_enum=False,
)
scan_mode = sa.Enum(
    "quick", "standard", "deep",
    name="scan_mode", native_enum=False,
)
severity = sa.Enum(
    "critical", "high", "medium", "low", "info",
    name="severity", native_enum=False,
)


def upgrade() -> None:
    # gen_random_uuid() lives in pgcrypto; enable it before any table uses it.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --- users -----------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("github_token", sa.String(length=1024), nullable=True),
        sa.Column("github_username", sa.String(length=255), nullable=True),
        sa.Column("subscription_tier", subscription_tier, server_default="free", nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_customer_id", name="uq_users_stripe_customer_id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- repositories ----------------------------------------------------
    op.create_table(
        "repositories",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("github_repo_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "github_repo_id", name="uq_repo_user_github"),
    )
    op.create_index("ix_repositories_user_id", "repositories", ["user_id"])

    # --- scans -----------------------------------------------------------
    op.create_table(
        "scans",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("repository_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("status", scan_status, server_default="pending", nullable=False),
        sa.Column("scan_mode", scan_mode, server_default="quick", nullable=False),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scans_repository_id", "scans", ["repository_id"])
    op.create_index("ix_scans_status", "scans", ["status"])

    # --- vulnerabilities -------------------------------------------------
    op.create_table(
        "vulnerabilities",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("scan_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("severity", severity, nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("poc_code", sa.Text(), nullable=True),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("owasp_category", sa.String(length=128), nullable=True),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("file_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vulnerabilities_scan_id", "vulnerabilities", ["scan_id"])
    op.create_index("ix_vulnerabilities_severity", "vulnerabilities", ["severity"])


def downgrade() -> None:
    # Drop in reverse dependency order. Table drops remove their own indexes.
    op.drop_table("vulnerabilities")
    op.drop_table("scans")
    op.drop_table("repositories")
    op.drop_table("users")
    # pgcrypto is intentionally left installed — it may be shared by other
    # objects, and dropping an extension can cascade unexpectedly.
