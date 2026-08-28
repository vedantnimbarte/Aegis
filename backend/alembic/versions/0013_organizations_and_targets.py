"""organizations, roles, audit log, and repositories generalized into targets

Two structural changes land together because the second depends on the first:

1. Tenancy moves from the user to an ``Organization``. Every existing user
   gets a personal organization and an OWNER membership, so nothing they own
   changes hands. Billing stays on the user; an organization reads its
   entitlement from ``owner_user_id``.

2. ``repositories`` becomes ``targets``: a repository is one *kind* of target
   alongside a live web app, an API, an LLM endpoint and an MCP server. The
   table is renamed rather than replaced so scan history, findings and triage
   verdicts survive intact — the alternative is asking every customer to
   re-baseline, which throws away the diffing that makes the product useful.

Also lands the columns the retest loop, evidence bundles, API tokens and
report shares need, so the schema settles in one release instead of six.

Revision ID: 0013_organizations_and_targets
Revises: 0012_outbound_webhook
Create Date: 2026-08-28
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0013_organizations_and_targets"
down_revision: Union[str, None] = "0012_outbound_webhook"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID(as_uuid=True)


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")
    )


def _rename_constraint(table: str, old: str, new: str) -> None:
    """Rename a constraint if it is still called ``old``.

    ``RENAME CONSTRAINT`` has no ``IF EXISTS``, and these are PostgreSQL's
    auto-generated names from migration 0001 — a convention, not a guarantee.
    A database whose constraints were named differently should be left alone
    rather than failing the whole migration over cosmetics.
    """
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{old}' AND conrelid = '{table}'::regclass
            ) THEN
                ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new};
            END IF;
        END $$;
        """
    )


# Constraints PostgreSQL named after the columns and table this migration
# renames. Left alone they would read `scans_repository_id_fkey` on a column
# called `target_id`, which is exactly the sort of stale name that misleads
# the next person to run `\\d scans`.
_CONSTRAINT_RENAMES = (
    ("targets", "repositories_pkey", "targets_pkey"),
    ("scans", "scans_repository_id_fkey", "scans_target_id_fkey"),
    ("schedules", "schedules_repository_id_fkey", "schedules_target_id_fkey"),
    (
        "greybox_configs",
        "greybox_configs_repository_id_fkey",
        "greybox_configs_target_id_fkey",
    ),
    (
        "finding_triage",
        "finding_triage_repository_id_fkey",
        "finding_triage_target_id_fkey",
    ),
)


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Organizations, memberships, audit log
    # ------------------------------------------------------------------
    op.create_table(
        "organizations",
        _uuid_pk(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False, unique=True),
        sa.Column(
            "owner_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("brand_name", sa.String(length=255), nullable=True),
        sa.Column("brand_primary_color", sa.String(length=16), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.create_index("ix_organizations_owner_user_id", "organizations", ["owner_user_id"])
    op.create_index("ix_organizations_parent_id", "organizations", ["parent_id"])

    op.create_table(
        "org_memberships",
        _uuid_pk(),
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("role", sa.String(length=32), server_default="member", nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )
    op.create_index(
        "ix_org_memberships_organization_id", "org_memberships", ["organization_id"]
    )
    op.create_index("ix_org_memberships_user_id", "org_memberships", ["user_id"])

    op.create_table(
        "audit_events",
        _uuid_pk(),
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("subject_type", sa.String(length=32), nullable=True),
        sa.Column("subject_id", sa.String(length=64), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_audit_events_organization_id", "audit_events", ["organization_id"]
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index(
        "ix_audit_org_created", "audit_events", ["organization_id", "created_at"]
    )

    # --- Backfill: a personal organization per existing user -------------
    # The slug is derived from the email local part, de-duplicated with a
    # short slice of the user id so two people named "alex" both get one.
    op.execute(
        """
        INSERT INTO organizations (id, name, slug, owner_user_id, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            split_part(u.email, '@', 1),
            regexp_replace(lower(split_part(u.email, '@', 1)), '[^a-z0-9]+', '-', 'g')
                || '-' || substr(replace(u.id::text, '-', ''), 1, 6),
            u.id,
            now(),
            now()
        FROM users u
        """
    )
    op.execute(
        """
        INSERT INTO org_memberships (id, organization_id, user_id, role, created_at, updated_at)
        SELECT gen_random_uuid(), o.id, o.owner_user_id, 'owner', now(), now()
        FROM organizations o
        """
    )

    # ------------------------------------------------------------------
    # 2. repositories -> targets
    # ------------------------------------------------------------------
    op.rename_table("repositories", "targets")
    op.execute("ALTER INDEX IF EXISTS ix_repositories_user_id RENAME TO ix_targets_user_id")

    op.add_column("targets", sa.Column("organization_id", UUID, nullable=True))
    op.add_column("targets", sa.Column("created_by_user_id", UUID, nullable=True))
    op.add_column(
        "targets",
        sa.Column("kind", sa.String(length=32), server_default="repo", nullable=False),
    )
    op.add_column("targets", sa.Column("provider", sa.String(length=32), nullable=True))
    op.add_column(
        "targets", sa.Column("external_repo_id", sa.String(length=64), nullable=True)
    )
    op.add_column("targets", sa.Column("clone_url", sa.String(length=1024), nullable=True))
    op.add_column("targets", sa.Column("openapi_url", sa.String(length=1024), nullable=True))
    op.add_column("targets", sa.Column("derived_spec", postgresql.JSONB(), nullable=True))
    op.add_column("targets", sa.Column("max_budget_usd", sa.Float(), nullable=True))
    op.add_column(
        "targets", sa.Column("gate_fail_severities", sa.String(length=128), nullable=True)
    )
    op.add_column(
        "targets",
        sa.Column(
            "gate_new_findings_only",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column("targets", sa.Column("discovered_from_id", UUID, nullable=True))
    op.add_column(
        "targets",
        sa.Column(
            "discovery_enabled",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    # Every existing row is a GitHub repository connected by its owner: the
    # old `url` was the clone URL, and `github_repo_id` the provider's id.
    op.execute(
        """
        UPDATE targets t
        SET organization_id = o.id,
            created_by_user_id = t.user_id,
            kind = 'repo',
            provider = 'github',
            external_repo_id = t.github_repo_id,
            clone_url = t.url
        FROM organizations o
        WHERE o.owner_user_id = t.user_id
        """
    )
    op.alter_column("targets", "organization_id", nullable=False)
    # `url` now means "the live endpoint", which a legacy repo row does not
    # have — the clone URL moved to its own column above. Drop the NOT NULL
    # *before* clearing the values: the old repositories.url was NOT NULL, so
    # the update would violate the constraint it is about to make obsolete.
    op.alter_column("targets", "url", existing_type=sa.String(length=1024), nullable=True)
    op.execute("UPDATE targets SET url = NULL")

    op.drop_constraint("uq_repo_user_github", "targets", type_="unique")
    op.drop_column("targets", "github_repo_id")
    op.drop_column("targets", "user_id")

    op.create_foreign_key(
        "fk_targets_organization",
        "targets",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_targets_created_by",
        "targets",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_targets_discovered_from",
        "targets",
        "targets",
        ["discovered_from_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_targets_organization_id", "targets", ["organization_id"])
    op.create_index("ix_targets_kind", "targets", ["kind"])
    op.create_unique_constraint(
        "uq_target_org_external_repo", "targets", ["organization_id", "external_repo_id"]
    )

    # --- Rename the columns that pointed at a repository -----------------
    for table, index in (
        ("scans", "ix_scans_repository_id"),
        ("schedules", "ix_schedules_repository_id"),
        ("finding_triage", "ix_finding_triage_repository_id"),
        ("greybox_configs", "ix_greybox_configs_repository_id"),
    ):
        op.alter_column(table, "repository_id", new_column_name="target_id")
        op.execute(
            f"ALTER INDEX IF EXISTS {index} RENAME TO ix_{table}_target_id"
        )

    op.execute(
        "ALTER TABLE finding_triage RENAME CONSTRAINT uq_triage_repo_finding "
        "TO uq_triage_target_finding"
    )
    op.execute(
        "ALTER TABLE greybox_configs RENAME CONSTRAINT uq_greybox_repository "
        "TO uq_greybox_target"
    )
    op.execute(
        "ALTER TABLE schedules RENAME CONSTRAINT uq_schedule_repository "
        "TO uq_schedule_target"
    )

    for table, old, new in _CONSTRAINT_RENAMES:
        _rename_constraint(table, old, new)

    # ------------------------------------------------------------------
    # 3. Scans: authorship, retests, engine provenance, attack chains
    # ------------------------------------------------------------------
    op.add_column("scans", sa.Column("created_by_user_id", UUID, nullable=True))
    op.create_foreign_key(
        "fk_scans_created_by", "scans", "users", ["created_by_user_id"], ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "scans", sa.Column("retest_fingerprint", sa.String(length=64), nullable=True)
    )
    op.create_index("ix_scans_retest_fingerprint", "scans", ["retest_fingerprint"])
    op.add_column("scans", sa.Column("retest_outcome", sa.String(length=32), nullable=True))
    op.add_column("scans", sa.Column("engine_model", sa.String(length=128), nullable=True))
    op.add_column("scans", sa.Column("attack_chains", postgresql.JSONB(), nullable=True))

    # ------------------------------------------------------------------
    # 4. Evidence on findings; retest verdicts and tracker keys on triage
    # ------------------------------------------------------------------
    op.add_column("vulnerabilities", sa.Column("evidence", postgresql.JSONB(), nullable=True))

    op.add_column(
        "finding_triage", sa.Column("issue_tracker", sa.String(length=32), nullable=True)
    )
    op.add_column("finding_triage", sa.Column("issue_key", sa.String(length=64), nullable=True))
    op.add_column(
        "finding_triage", sa.Column("retest_outcome", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "finding_triage",
        sa.Column("retested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("finding_triage", sa.Column("last_retest_scan_id", UUID, nullable=True))
    op.add_column(
        "finding_triage", sa.Column("retest_evidence", postgresql.JSONB(), nullable=True)
    )
    op.create_foreign_key(
        "fk_triage_retest_scan",
        "finding_triage",
        "scans",
        ["last_retest_scan_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # 5. Installations move from a user to an organization
    # ------------------------------------------------------------------
    op.add_column("installations", sa.Column("organization_id", UUID, nullable=True))
    op.alter_column("installations", "user_id", new_column_name="claimed_by_user_id")
    op.execute(
        """
        UPDATE installations i
        SET organization_id = o.id
        FROM organizations o
        WHERE o.owner_user_id = i.claimed_by_user_id
        """
    )
    # An installation whose claimer vanished cannot route webhooks anywhere.
    op.execute("DELETE FROM installations WHERE organization_id IS NULL")
    op.alter_column("installations", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_installations_organization",
        "installations",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_installations_organization_id", "installations", ["organization_id"]
    )

    # ------------------------------------------------------------------
    # 6. New user columns: other git hosts, issue trackers, purchased units
    # ------------------------------------------------------------------
    for column in (
        sa.Column("gitlab_token", sa.String(length=1024), nullable=True),
        sa.Column("bitbucket_token", sa.String(length=1024), nullable=True),
        sa.Column("jira_url", sa.String(length=512), nullable=True),
        sa.Column("jira_email", sa.String(length=320), nullable=True),
        sa.Column("jira_api_token", sa.String(length=1024), nullable=True),
        sa.Column("jira_project_key", sa.String(length=32), nullable=True),
        sa.Column("linear_api_key", sa.String(length=1024), nullable=True),
        sa.Column("linear_team_id", sa.String(length=64), nullable=True),
        sa.Column("purchased_seats", sa.Integer(), nullable=True),
        sa.Column("purchased_scan_credits", sa.Integer(), nullable=True),
    ):
        op.add_column("users", column)

    # ------------------------------------------------------------------
    # 7. API tokens and report shares
    # ------------------------------------------------------------------
    op.create_table(
        "api_tokens",
        _uuid_pk(),
        sa.Column(
            "organization_id",
            UUID,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("token_prefix", sa.String(length=16), nullable=False),
        sa.Column("role", sa.String(length=32), server_default="member", nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_api_tokens_organization_id", "api_tokens", ["organization_id"])
    op.create_index("ix_api_tokens_token_hash", "api_tokens", ["token_hash"], unique=True)

    op.create_table(
        "report_shares",
        _uuid_pk(),
        sa.Column(
            "scan_id", UUID, sa.ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "created_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "include_poc", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("view_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_report_shares_scan_id", "report_shares", ["scan_id"])
    op.create_index(
        "ix_report_shares_token_hash", "report_shares", ["token_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_table("report_shares")
    op.drop_table("api_tokens")

    for name in (
        "purchased_scan_credits",
        "purchased_seats",
        "linear_team_id",
        "linear_api_key",
        "jira_project_key",
        "jira_api_token",
        "jira_email",
        "jira_url",
        "bitbucket_token",
        "gitlab_token",
    ):
        op.drop_column("users", name)

    op.drop_constraint("fk_installations_organization", "installations", type_="foreignkey")
    op.drop_index("ix_installations_organization_id", table_name="installations")
    op.drop_column("installations", "organization_id")
    op.alter_column("installations", "claimed_by_user_id", new_column_name="user_id")

    op.drop_constraint("fk_triage_retest_scan", "finding_triage", type_="foreignkey")
    for name in (
        "retest_evidence",
        "last_retest_scan_id",
        "retested_at",
        "retest_outcome",
        "issue_key",
        "issue_tracker",
    ):
        op.drop_column("finding_triage", name)
    op.drop_column("vulnerabilities", "evidence")

    op.drop_column("scans", "attack_chains")
    op.drop_column("scans", "engine_model")
    op.drop_column("scans", "retest_outcome")
    op.drop_index("ix_scans_retest_fingerprint", table_name="scans")
    op.drop_column("scans", "retest_fingerprint")
    op.drop_constraint("fk_scans_created_by", "scans", type_="foreignkey")
    op.drop_column("scans", "created_by_user_id")

    for table, old, new in _CONSTRAINT_RENAMES:
        _rename_constraint(table, new, old)

    op.execute(
        "ALTER TABLE schedules RENAME CONSTRAINT uq_schedule_target "
        "TO uq_schedule_repository"
    )
    op.execute(
        "ALTER TABLE greybox_configs RENAME CONSTRAINT uq_greybox_target "
        "TO uq_greybox_repository"
    )
    op.execute(
        "ALTER TABLE finding_triage RENAME CONSTRAINT uq_triage_target_finding "
        "TO uq_triage_repo_finding"
    )
    for table in ("scans", "schedules", "finding_triage", "greybox_configs"):
        op.alter_column(table, "target_id", new_column_name="repository_id")
        op.execute(
            f"ALTER INDEX IF EXISTS ix_{table}_target_id "
            f"RENAME TO ix_{table}_repository_id"
        )

    # Non-repo targets have no place in a repositories table; they are dropped
    # along with their scans (the FK cascades).
    op.execute("DELETE FROM targets WHERE kind <> 'repo'")
    op.add_column("targets", sa.Column("user_id", UUID, nullable=True))
    op.add_column("targets", sa.Column("github_repo_id", sa.String(length=64), nullable=True))
    op.execute(
        """
        UPDATE targets t
        SET user_id = o.owner_user_id,
            github_repo_id = t.external_repo_id,
            url = t.clone_url
        FROM organizations o
        WHERE o.id = t.organization_id
        """
    )
    op.alter_column("targets", "user_id", nullable=False)
    op.alter_column("targets", "github_repo_id", nullable=False)
    op.alter_column("targets", "url", existing_type=sa.String(length=1024), nullable=False)

    op.drop_constraint("uq_target_org_external_repo", "targets", type_="unique")
    op.drop_constraint("fk_targets_discovered_from", "targets", type_="foreignkey")
    op.drop_constraint("fk_targets_created_by", "targets", type_="foreignkey")
    op.drop_constraint("fk_targets_organization", "targets", type_="foreignkey")
    op.drop_index("ix_targets_kind", table_name="targets")
    op.drop_index("ix_targets_organization_id", table_name="targets")
    for name in (
        "discovery_enabled",
        "discovered_from_id",
        "gate_new_findings_only",
        "gate_fail_severities",
        "max_budget_usd",
        "derived_spec",
        "openapi_url",
        "clone_url",
        "external_repo_id",
        "provider",
        "kind",
        "created_by_user_id",
        "organization_id",
    ):
        op.drop_column("targets", name)
    op.create_unique_constraint(
        "uq_repo_user_github", "targets", ["user_id", "github_repo_id"]
    )
    op.execute("ALTER INDEX IF EXISTS ix_targets_user_id RENAME TO ix_repositories_user_id")
    op.rename_table("targets", "repositories")

    op.drop_table("audit_events")
    op.drop_table("org_memberships")
    op.drop_table("organizations")
