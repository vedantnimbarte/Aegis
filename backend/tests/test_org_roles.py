"""Role ordering and target-kind validation — the rules behind the RBAC gate."""
from __future__ import annotations

import pytest

from app.models.enums import ROLE_RANK, OrgRole, TargetKind
from app.models.target import missing_fields
from app.services import org_service, target_service


def test_roles_are_ordered_least_to_most_privileged() -> None:
    assert (
        ROLE_RANK[OrgRole.VIEWER]
        < ROLE_RANK[OrgRole.MEMBER]
        < ROLE_RANK[OrgRole.ADMIN]
        < ROLE_RANK[OrgRole.OWNER]
    )


def test_every_role_has_a_rank() -> None:
    # A role with no rank would silently fail every "at least this role" check.
    assert set(ROLE_RANK) == set(OrgRole)


def test_slugify_is_url_safe_and_never_empty() -> None:
    assert org_service.slugify("Acme Inc.") == "acme-inc"
    assert org_service.slugify("  ") == "org"
    assert org_service.slugify("!!!") == "org"


def test_a_repo_target_needs_a_clone_url() -> None:
    assert missing_fields(TargetKind.REPO, {}) == ["clone_url"]
    assert missing_fields(TargetKind.REPO, {"clone_url": "https://x/y.git"}) == []


def test_endpoint_targets_need_a_url() -> None:
    for kind in (TargetKind.WEB, TargetKind.API, TargetKind.LLM, TargetKind.MCP):
        assert missing_fields(kind, {}) == ["url"]
        assert missing_fields(kind, {"url": "https://x.test"}) == []


def test_blank_strings_do_not_satisfy_a_requirement() -> None:
    assert missing_fields(TargetKind.WEB, {"url": "   "}) == ["url"]


def test_validate_rejects_a_repo_with_no_provider() -> None:
    with pytest.raises(target_service.TargetValidationError):
        target_service.validate(TargetKind.REPO, {"clone_url": "https://x/y.git"})


def test_validate_accepts_a_complete_repo() -> None:
    target_service.validate(
        TargetKind.REPO, {"clone_url": "https://x/y.git", "provider": "github"}
    )


def test_default_name_for_an_endpoint_is_its_host() -> None:
    """"api.acme.com" reads better in a list than a full URL with query string."""
    name = target_service.default_name_for(
        TargetKind.WEB, {"url": "https://api.acme.com/v1/health?x=1"}
    )
    assert name == "api.acme.com"


def test_an_explicit_name_wins() -> None:
    name = target_service.default_name_for(
        TargetKind.WEB, {"url": "https://api.acme.com", "name": "Checkout API"}
    )
    assert name == "Checkout API"
