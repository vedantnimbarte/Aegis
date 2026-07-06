"""auto-fix: suggested_fix on vulnerabilities + autofix_pr_url on scans

Revision ID: 0007_autofix
Revises: 0006_greybox
Create Date: 2026-07-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007_autofix"
down_revision: Union[str, None] = "0006_greybox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vulnerabilities",
        sa.Column("suggested_fix", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "scans", sa.Column("autofix_pr_url", sa.String(length=1024), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("scans", "autofix_pr_url")
    op.drop_column("vulnerabilities", "suggested_fix")
