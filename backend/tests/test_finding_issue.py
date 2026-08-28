"""Tests for the GitHub issue body built from a finding (services/finding_issue.py)."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.models.enums import Severity
from app.services.finding_issue import issue_body, issue_title


def _vuln(**overrides) -> SimpleNamespace:
    base = dict(
        severity=Severity.HIGH,
        title="SQL injection in the login form",
        description="User input reaches the query unescaped.",
        poc_code=None,
        remediation=None,
        owasp_category="A03:2021",
        cvss_score=8.6,
        file_path="app/db.py",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_title_carries_the_severity() -> None:
    assert issue_title(_vuln()) == "[Aegis/High] SQL injection in the login form"


def test_body_has_metadata_description_and_a_link_back() -> None:
    scan = SimpleNamespace(id=uuid.uuid4())
    body = issue_body(scan, _vuln())
    assert "**Severity:** High" in body
    assert "**CVSS:** 8.6" in body
    assert "`app/db.py`" in body
    assert "## Description" in body
    assert "User input reaches the query unescaped." in body
    assert f"/scans/{scan.id}" in body
    # Optional sections stay out when the finding has nothing to put in them.
    assert "## Proof of concept" not in body
    assert "## Remediation" not in body


def test_optional_sections_appear_when_present() -> None:
    scan = SimpleNamespace(id=uuid.uuid4())
    body = issue_body(
        scan, _vuln(poc_code="' OR 1=1 --", remediation="Use bound parameters.")
    )
    assert "## Proof of concept" in body
    assert "' OR 1=1 --" in body
    assert "## Remediation" in body
    assert "Use bound parameters." in body
