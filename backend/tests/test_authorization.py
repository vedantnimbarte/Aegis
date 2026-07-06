"""Scan-authorization gate (deps.ensure_scan_authorized)."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import deps
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
