"""user display name

A profile needs something to change other than the address you sign in with.
Nullable: existing accounts have no name, and the UI falls back to the email
local part rather than inventing one.

Revision ID: 0014_user_display_name
Revises: 0013_organizations_and_targets
Create Date: 2026-08-29
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0014_user_display_name"
down_revision: Union[str, None] = "0013_organizations_and_targets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "display_name")
