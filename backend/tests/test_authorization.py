"""Authorization gates: scan attestation, and the organization role check."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import deps
from app.models.enums import OrgRole
from app.models.user import User


def test_property_reflects_timestamp():
    assert User(scan_terms_accepted_at=None).has_accepted_scan_terms is False
    assert User(scan_terms_accepted_at=datetime.now(timezone.utc)).has_accepted_scan_terms is True


def test_gate_blocks_when_not_accepted():
    user = SimpleNamespace(has_accepted_scan_terms=False)
    with pytest.raises(HTTPException) as exc:
        deps.ensure_scan_authorized(user)
    assert exc.value.status_code == 403
    assert exc.value.detail["reason"] == "scan_terms_required"


def test_gate_allows_when_accepted():
    user = SimpleNamespace(has_accepted_scan_terms=True)
    deps.ensure_scan_authorized(user)  # must not raise


# --- Role gate -----------------------------------------------------------
def _principal(role: OrgRole, user=None) -> deps.Principal:
    return deps.Principal(
        organization=SimpleNamespace(id="org", name="Acme"),
        role=role,
        user=user,
        via_token=user is None,
    )


@pytest.mark.parametrize(
    "role, minimum, allowed",
    [
        (OrgRole.VIEWER, OrgRole.VIEWER, True),
        (OrgRole.VIEWER, OrgRole.MEMBER, False),
        (OrgRole.MEMBER, OrgRole.VIEWER, True),
        (OrgRole.MEMBER, OrgRole.ADMIN, False),
        (OrgRole.ADMIN, OrgRole.MEMBER, True),
        (OrgRole.ADMIN, OrgRole.OWNER, False),
        (OrgRole.OWNER, OrgRole.OWNER, True),
    ],
)
def test_require_role_enforces_the_rank(role, minimum, allowed):
    dependency = deps.require_role(minimum)
    principal = _principal(role)
    if allowed:
        assert dependency(principal) is principal
    else:
        with pytest.raises(HTTPException) as exc:
            dependency(principal)
        assert exc.value.status_code == 403
        assert exc.value.detail["reason"] == "insufficient_role"
        assert exc.value.detail["required_role"] == minimum.value


def test_a_viewer_cannot_spend_or_attack():
    """The auditor seat: reads reports, cannot launch a scan."""
    with pytest.raises(HTTPException):
        deps.require_member(_principal(OrgRole.VIEWER))
    assert deps.require_viewer(_principal(OrgRole.VIEWER)) is not None


def test_scan_gate_requires_a_verified_email_for_a_human():
    user = SimpleNamespace(
        email_verified=False, has_accepted_scan_terms=True, email="a@b.c"
    )
    with pytest.raises(HTTPException) as exc:
        deps.ensure_can_scan(_principal(OrgRole.MEMBER, user), db=None)
    assert exc.value.detail["reason"] == "email_not_verified"


def test_scan_gate_lets_a_token_inherit_the_owner_attestation(monkeypatch):
    """CI cannot click a checkbox; the person who issued the token already did."""
    owner = SimpleNamespace(
        email_verified=False, has_accepted_scan_terms=True, email="owner@b.c"
    )
    monkeypatch.setattr(deps, "billing_user_for", lambda db, principal: owner)
    # Unverified owner email must not block a token: it proves a human's
    # address, which a pipeline does not have.
    deps.ensure_can_scan(_principal(OrgRole.MEMBER), db=None)


def test_scan_gate_blocks_a_token_when_nobody_attested(monkeypatch):
    owner = SimpleNamespace(
        email_verified=True, has_accepted_scan_terms=False, email="owner@b.c"
    )
    monkeypatch.setattr(deps, "billing_user_for", lambda db, principal: owner)
    with pytest.raises(HTTPException) as exc:
        deps.ensure_can_scan(_principal(OrgRole.MEMBER), db=None)
    assert exc.value.detail["reason"] == "scan_terms_required"
