"""generic outbound webhook url + signing secret on users

Revision ID: 0012_outbound_webhook
Revises: 0011_finding_issue_url
Create Date: 2026-08-28
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0012_outbound_webhook"
down_revision: Union[str, None] = "0011_finding_issue_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # One signed POST per finished scan. The secret is an EncryptedString on
    # the model, which stores ciphertext in a plain VARCHAR (see 0008).
    op.add_column("users", sa.Column("webhook_url", sa.String(length=1024), nullable=True))
    op.add_column("users", sa.Column("webhook_secret", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "webhook_secret")
    op.drop_column("users", "webhook_url")
