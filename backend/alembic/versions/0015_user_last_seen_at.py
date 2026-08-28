"""user last seen at

Stateless JWTs leave nothing to count when someone asks "who is signed in?".
This column is the honest substitute: the last authenticated request, written
at most once every few minutes per user. Nullable — every existing account has
never been observed under the new code.

Revision ID: 0015_user_last_seen_at
Revises: 0014_user_display_name
Create Date: 2026-08-29
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0015_user_last_seen_at"
down_revision: Union[str, None] = "0014_user_display_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "last_seen_at")
