"""recurring scan schedules

Revision ID: 0004_schedules
Revises: 0003_email_verified
Create Date: 2026-07-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_schedules"
down_revision: Union[str, None] = "0003_email_verified"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


scan_mode = sa.Enum(
    "quick", "standard", "deep", name="scan_mode", native_enum=False,
)
scan_frequency = sa.Enum(
    "daily", "weekly", "monthly", name="scan_frequency", native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("repository_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_mode", scan_mode, server_default="quick", nullable=False),
        sa.Column("frequency", scan_frequency, server_default="weekly", nullable=False),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", name="uq_schedule_repository"),
    )
    op.create_index("ix_schedules_repository_id", "schedules", ["repository_id"])
    op.create_index("ix_schedules_next_run_at", "schedules", ["next_run_at"])


def downgrade() -> None:
    op.drop_table("schedules")
