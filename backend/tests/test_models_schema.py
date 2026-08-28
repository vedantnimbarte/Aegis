"""Model wiring: mappers configure, and the schema is shaped as intended.

SQLAlchemy configures mappers lazily, so a broken relationship (an ambiguous
join, a missing ``foreign_keys``, a self-reference with no ``remote_side``)
stays silent until the first query at runtime. ``configure_mappers()`` forces
it here instead.

No database required — this reads metadata only.
"""
from __future__ import annotations

import pytest
from sqlalchemy.orm import configure_mappers

from app import models
from app.db.base_class import Base


def test_every_mapper_configures() -> None:
    configure_mappers()


def test_expected_tables_exist() -> None:
    tables = set(Base.metadata.tables)
    assert {
        "users",
        "organizations",
        "org_memberships",
        "audit_events",
        "api_tokens",
        "report_shares",
        "targets",
        "scans",
        "vulnerabilities",
        "finding_triage",
        "schedules",
        "greybox_configs",
        "installations",
    } <= tables
    # The rename is the point of the migration: nothing should still be
    # writing to a repositories table.
    assert "repositories" not in tables


@pytest.mark.parametrize(
    "table, column, references",
    [
        ("targets", "organization_id", "organizations.id"),
        ("scans", "target_id", "targets.id"),
        ("finding_triage", "target_id", "targets.id"),
        ("schedules", "target_id", "targets.id"),
        ("greybox_configs", "target_id", "targets.id"),
        ("vulnerabilities", "scan_id", "scans.id"),
        ("org_memberships", "organization_id", "organizations.id"),
        ("installations", "organization_id", "organizations.id"),
        ("api_tokens", "organization_id", "organizations.id"),
        ("report_shares", "scan_id", "scans.id"),
        ("audit_events", "organization_id", "organizations.id"),
    ],
)
def test_tenancy_foreign_keys(table: str, column: str, references: str) -> None:
    """Every row must be reachable only through an organization.

    These are the joins tenant isolation is enforced over, so a missing or
    misdirected one is a cross-tenant read waiting to happen.
    """
    col = Base.metadata.tables[table].columns[column]
    assert {str(fk.target_fullname) for fk in col.foreign_keys} == {references}


def test_deleting_an_organization_cascades_to_its_data() -> None:
    fk = list(Base.metadata.tables["targets"].columns["organization_id"].foreign_keys)[0]
    assert fk.ondelete == "CASCADE"


def test_actor_references_survive_a_deleted_user() -> None:
    """An audit row must outlive the person it names, or the log rewrites
    itself every time somebody leaves."""
    fk = list(Base.metadata.tables["audit_events"].columns["actor_user_id"].foreign_keys)[0]
    assert fk.ondelete == "SET NULL"


def test_new_columns_are_present() -> None:
    scans = Base.metadata.tables["scans"].columns
    assert {"retest_fingerprint", "retest_outcome", "engine_model", "attack_chains"} <= set(
        scans.keys()
    )
    assert "evidence" in Base.metadata.tables["vulnerabilities"].columns
    triage = Base.metadata.tables["finding_triage"].columns
    assert {"retest_outcome", "retested_at", "issue_tracker"} <= set(triage.keys())


def test_credentials_are_stored_encrypted() -> None:
    """Every secret on the user row goes through EncryptedString, not VARCHAR."""
    from app.core.encryption import EncryptedString

    users = Base.metadata.tables["users"].columns
    for name in (
        "github_token",
        "gitlab_token",
        "bitbucket_token",
        "llm_api_key",
        "webhook_secret",
        "jira_api_token",
        "linear_api_key",
    ):
        assert isinstance(users[name].type, EncryptedString), name


def test_model_registry_exports_the_new_models() -> None:
    for name in ("Organization", "OrgMembership", "AuditEvent", "ApiToken", "Target"):
        assert hasattr(models, name)
