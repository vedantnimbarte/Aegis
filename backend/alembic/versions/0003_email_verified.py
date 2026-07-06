"""email verification: users.email_verified

Revision ID: 0003_email_verified
Revises: 0002_subscription_fields
Create Date: 2026-07-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_email_verified"
down_revision: Union[str, None] = "0002_subscription_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    # Existing accounts predate verification — treat them as verified so the
    # new scan gate doesn't lock anyone out.
    op.execute("UPDATE users SET email_verified = true")


def downgrade() -> None:
    op.drop_column("users", "email_verified")
