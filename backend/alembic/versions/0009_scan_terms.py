"""scan authorization: users.scan_terms_accepted_at

Revision ID: 0009_scan_terms
Revises: 0008_integrations
Create Date: 2026-07-07
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0009_scan_terms"
down_revision: Union[str, None] = "0008_integrations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # When the user accepted the scan-authorization terms (NULL = not yet).
    op.add_column(
        "users",
        sa.Column("scan_terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "scan_terms_accepted_at")
