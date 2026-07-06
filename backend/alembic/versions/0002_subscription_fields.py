"""subscription fields: status, stripe subscription id, current period end

Revision ID: 0002_subscription_fields
Revises: 0001_initial_schema
Create Date: 2026-07-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_subscription_fields"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


subscription_status = sa.Enum(
    "none", "trialing", "active", "past_due", "canceled", "incomplete",
    name="subscription_status", native_enum=False,
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "subscription_status",
            subscription_status,
            server_default="none",
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("stripe_subscription_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "subscription_current_period_end",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_unique_constraint(
        "uq_users_stripe_subscription_id", "users", ["stripe_subscription_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_stripe_subscription_id", "users", type_="unique")
    op.drop_column("users", "subscription_current_period_end")
    op.drop_column("users", "stripe_subscription_id")
    op.drop_column("users", "subscription_status")
