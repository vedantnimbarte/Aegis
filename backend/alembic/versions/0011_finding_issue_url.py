"""github issue url on finding triage

Revision ID: 0011_finding_issue_url
Revises: 0010_triage_and_usage
Create Date: 2026-08-28
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0011_finding_issue_url"
down_revision: Union[str, None] = "0010_triage_and_usage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "finding_triage",
        sa.Column("github_issue_url", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("finding_triage", "github_issue_url")
