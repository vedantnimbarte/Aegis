"""finding triage, vulnerability fingerprints, and per-scan LLM usage

Revision ID: 0010_triage_and_usage
Revises: 0009_scan_terms
Create Date: 2026-08-28
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010_triage_and_usage"
down_revision: Union[str, None] = "0009_scan_terms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Per-scan LLM usage, captured from Strix's run.json ---------------
    op.add_column("scans", sa.Column("cost_usd", sa.Float(), nullable=True))
    op.add_column("scans", sa.Column("llm_requests", sa.Integer(), nullable=True))
    op.add_column("scans", sa.Column("input_tokens", sa.BigInteger(), nullable=True))
    op.add_column("scans", sa.Column("output_tokens", sa.BigInteger(), nullable=True))

    # --- Stable finding identity across re-scans -------------------------
    op.add_column(
        "vulnerabilities", sa.Column("fingerprint", sa.String(length=64), nullable=True)
    )
    op.create_index(
        "ix_vulnerabilities_fingerprint", "vulnerabilities", ["fingerprint"]
    )

    # --- Triage verdicts, keyed by repo + fingerprint --------------------
    op.create_table(
        "finding_triage",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "repository_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default="open", nullable=False
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "repository_id", "fingerprint", name="uq_triage_repo_finding"
        ),
    )
    op.create_index("ix_finding_triage_repository_id", "finding_triage", ["repository_id"])
    op.create_index("ix_finding_triage_fingerprint", "finding_triage", ["fingerprint"])

    # Backfill fingerprints for findings ingested before this column existed,
    # so pre-existing scans can still be diffed and triaged. Mirrors
    # services/finding_identity.fingerprint(): sha256 over the normalized
    # title, file path, and classification joined by US (0x1f).
    op.execute(
        """
        UPDATE vulnerabilities
        SET fingerprint = encode(
            sha256(
                convert_to(
                    concat_ws(
                        chr(31),
                        lower(btrim(regexp_replace(coalesce(title, ''), '\s+', ' ', 'g'))),
                        lower(btrim(regexp_replace(coalesce(file_path, ''), '\s+', ' ', 'g'))),
                        lower(btrim(regexp_replace(coalesce(owasp_category, ''), '\s+', ' ', 'g')))
                    ),
                    'UTF8'
                )
            ),
            'hex'
        )
        WHERE fingerprint IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_finding_triage_fingerprint", table_name="finding_triage")
    op.drop_index("ix_finding_triage_repository_id", table_name="finding_triage")
    op.drop_table("finding_triage")
    op.drop_index("ix_vulnerabilities_fingerprint", table_name="vulnerabilities")
    op.drop_column("vulnerabilities", "fingerprint")
    op.drop_column("scans", "output_tokens")
    op.drop_column("scans", "input_tokens")
    op.drop_column("scans", "llm_requests")
    op.drop_column("scans", "cost_usd")
