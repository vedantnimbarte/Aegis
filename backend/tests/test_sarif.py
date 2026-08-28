"""Tests for the SARIF exporter (services/sarif.py).

Duck-typed SimpleNamespace stand-ins, so no DB is needed — same approach as
test_report_pdf.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.services import sarif


def _vuln(**kw):
    base = dict(
        severity="high",
        title="SQL injection in login",
        description="User input reaches the query unescaped.",
        remediation=None,
        owasp_category=None,
        cvss_score=None,
        file_path="app/auth.py",
        fingerprint="a" * 64,
        triage_status="open",
        triage_note=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _report(*vulns):
    return SimpleNamespace(
        scan=SimpleNamespace(id="3f1c9a20-0000-4000-8000-000000000001"),
        vulnerabilities=list(vulns),
    )


def test_document_shape_is_sarif_210() -> None:
    doc = sarif.build_sarif(_report(_vuln()), "acme/api")

    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["tool"]["driver"]["name"] == "Aegis"
    assert doc["runs"][0]["properties"]["repository"] == "acme/api"


def test_severity_maps_to_sarif_level_and_security_severity() -> None:
    doc = sarif.build_sarif(
        _report(
            _vuln(severity="critical", fingerprint="c" * 64),
            _vuln(severity="medium", fingerprint="m" * 64),
            _vuln(severity="info", fingerprint="i" * 64),
        ),
        "acme/api",
    )
    levels = [r["level"] for r in doc["runs"][0]["results"]]
    assert levels == ["error", "warning", "note"]

    # GitHub buckets alerts off security-severity, so it must be populated.
    rules = doc["runs"][0]["tool"]["driver"]["rules"]
    assert all(r["properties"]["security-severity"] for r in rules)


def test_cvss_score_overrides_the_severity_fallback() -> None:
    doc = sarif.build_sarif(_report(_vuln(cvss_score=8.8)), "acme/api")
    rule = doc["runs"][0]["tool"]["driver"]["rules"][0]
    assert rule["properties"]["security-severity"] == "8.8"


def test_triaged_findings_are_suppressed_with_their_note() -> None:
    doc = sarif.build_sarif(
        _report(
            _vuln(triage_status="false_positive", triage_note="Test fixture, not prod"),
            _vuln(fingerprint="b" * 64),  # untouched, stays open
        ),
        "acme/api",
    )
    first, second = doc["runs"][0]["results"]

    assert first["suppressions"][0]["justification"] == "Test fixture, not prod"
    assert "suppressions" not in second


def test_same_fingerprint_collapses_to_one_rule_with_two_results() -> None:
    doc = sarif.build_sarif(_report(_vuln(), _vuln()), "acme/api")
    run = doc["runs"][0]

    assert len(run["tool"]["driver"]["rules"]) == 1
    assert len(run["results"]) == 2


def test_fingerprint_is_emitted_so_github_tracks_one_alert_over_time() -> None:
    doc = sarif.build_sarif(_report(_vuln()), "acme/api")
    result = doc["runs"][0]["results"][0]
    assert result["partialFingerprints"]["aegisFingerprint/v1"] == "a" * 64


def test_finding_without_a_file_still_gets_a_location() -> None:
    # DAST findings have no file; GitHub drops results with no location.
    doc = sarif.build_sarif(_report(_vuln(file_path=None)), "acme/api")
    location = doc["runs"][0]["results"][0]["locations"][0]
    assert location["physicalLocation"]["artifactLocation"]["uri"] == "."


def test_empty_report_is_still_a_valid_document() -> None:
    doc = sarif.build_sarif(_report(), "acme/api")
    assert doc["runs"][0]["results"] == []
    assert doc["runs"][0]["tool"]["driver"]["rules"] == []
