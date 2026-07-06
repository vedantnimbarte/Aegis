"""github app: installations table + pull-request scan context

Revision ID: 0005_github_app
Revises: 0004_schedules
Create Date: 2026-07-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005_github_app"
down_revision: Union[str, None] = "0004_schedules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


scan_trigger = sa.Enum(
    "manual", "scheduled", "pull_request", name="scan_trigger", native_enum=False,
)


def upgrade() -> None:
    # --- installations ---------------------------------------------------
    op.create_table(
        "installations",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("installation_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("account_login", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("installation_id", name="uq_installation_gh_id"),
    )
    op.create_index("ix_installations_installation_id", "installations", ["installation_id"], unique=True)
    op.create_index("ix_installations_user_id", "installations", ["user_id"])

    # --- pull-request context on scans -----------------------------------
    op.add_column(
        "scans",
        sa.Column("trigger", scan_trigger, server_default="manual", nullable=False),
    )
    op.add_column("scans", sa.Column("github_installation_id", sa.String(length=64), nullable=True))
    op.add_column("scans", sa.Column("github_pr_number", sa.Integer(), nullable=True))
    op.add_column("scans", sa.Column("github_commit_sha", sa.String(length=64), nullable=True))
    op.add_column("scans", sa.Column("github_check_run_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("scans", "github_check_run_id")
    op.drop_column("scans", "github_commit_sha")
    op.drop_column("scans", "github_pr_number")
    op.drop_column("scans", "github_installation_id")
    op.drop_column("scans", "trigger")
    op.drop_table("installations")
