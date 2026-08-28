"""account-level audit events

Signing in is not something you do *to* an organization, and a failed sign-in
may not resolve to a user at all — so the audit log's organization is now
optional. Org history queries filter on the column, so these events simply
never appear in an org's log.

Revision ID: 0016_account_level_audit_events
Revises: 0015_user_last_seen_at
Create Date: 2026-08-29
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0016_account_level_audit_events"
down_revision: Union[str, None] = "0015_user_last_seen_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "audit_events",
        "organization_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    # Account-level rows have no organization to fall back to, and inventing
    # one would be a lie in a security log. Drop them.
    op.execute(sa.text("DELETE FROM audit_events WHERE organization_id IS NULL"))
    op.alter_column(
        "audit_events",
        "organization_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
