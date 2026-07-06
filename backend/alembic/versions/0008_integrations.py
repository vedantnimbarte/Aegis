"""integrations: BYOK LLM key/model and Slack webhook on users

Revision ID: 0008_integrations
Revises: 0007_autofix
Create Date: 2026-07-06
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008_integrations"
down_revision: Union[str, None] = "0007_autofix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # BYOK (Pro/Enterprise): user-supplied LLM model + key (encrypted at rest).
    op.add_column("users", sa.Column("llm_model", sa.String(length=128), nullable=True))
    op.add_column("users", sa.Column("llm_api_key", sa.String(length=1024), nullable=True))
    # Slack incoming-webhook URL for scan notifications (not a secret we decrypt,
    # but treated as sensitive: never returned by the API).
    op.add_column("users", sa.Column("slack_webhook_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "slack_webhook_url")
    op.drop_column("users", "llm_api_key")
    op.drop_column("users", "llm_model")
