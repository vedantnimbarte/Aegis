"""greybox authenticated-testing config

Revision ID: 0006_greybox
Revises: 0005_github_app
Create Date: 2026-07-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006_greybox"
down_revision: Union[str, None] = "0005_github_app"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "greybox_configs",
        sa.Column("id", sa.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("repository_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("target_url", sa.String(length=1024), nullable=False),
        sa.Column("login_url", sa.String(length=1024), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        # Encrypted at rest (AES-256-GCM) — stored as base64 text.
        sa.Column("password", sa.String(length=512), nullable=True),
        sa.Column("extra", sa.String(length=4096), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", name="uq_greybox_repository"),
    )
    op.create_index("ix_greybox_configs_repository_id", "greybox_configs", ["repository_id"])


def downgrade() -> None:
    op.drop_table("greybox_configs")
