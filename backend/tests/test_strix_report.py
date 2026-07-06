"""Tests for the Strix report parser (services/strix_report.py)."""
from __future__ import annotations

import json
from pathlib import Path

from app.models.enums import Severity
from app.services import strix_report


def _write_report(tmp_path: Path, findings) -> Path:
    run_dir = tmp_path / "strix_runs" / "run-abc"
    run_dir.mkdir(parents=True)
    (run_dir / strix_report.VULNERABILITIES_FILENAME).write_text(
        json.dumps(findings), encoding="utf-8"
    )
    return run_dir


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    run_dir = tmp_path / "strix_runs" / "run-empty"
    run_dir.mkdir(parents=True)
    assert strix_report.parse_report(run_dir) == []


def test_empty_array_returns_empty(tmp_path: Path) -> None:
    run_dir = _write_report(tmp_path, [])
    assert strix_report.parse_report(run_dir) == []


def test_full_finding_is_mapped(tmp_path: Path) -> None:
    run_dir = _write_report(
        tmp_path,
        [
            {
                "id": "vuln-0001",
                "title": "SQL Injection in /login",
                "severity": "critical",
                "description": "User input is concatenated into a SQL query.",
                "impact": "Full database read/write.",
                "technical_analysis": "The `username` parameter is not parameterized.",
                "poc_description": "Send ' OR 1=1-- as the username.",
                "poc_script_code": "curl -d \"username=' OR 1=1--\" https://x/login",
                "remediation_steps": ["Use parameterized queries.", "Validate input."],
                "cvss": 9.8,
                "cwe": "CWE-89",
                "method": "POST",
                "endpoint": "/login",
                "code_locations": [
                    {
                        "file": "app/auth.py",
                        "start_line": 42,
                        "end_line": 45,
                        "fix_before": "query = f\"... {username}\"",
                        "fix_after": "query = \"... %s\"; params=(username,)",
                    }
                ],
            }
        ],
    )

    (finding,) = strix_report.parse_report(run_dir)

    assert finding.severity is Severity.CRITICAL
    assert finding.title == "SQL Injection in /login"
    assert finding.cvss_score == 9.8
    assert finding.owasp_category == "CWE-89"
    assert finding.poc_code.startswith("curl")
    assert finding.file_path == "app/auth.py:42-45"
    # Remediation folds in the steps and the suggested diff.
    assert "parameterized queries" in finding.remediation
    assert "```diff" in finding.remediation
    # Description folds in the narrative sections.
    assert "### Impact" in finding.description
    assert "### Proof of concept" in finding.description
    assert "POST /login" in finding.description


def test_unknown_severity_defaults_to_info(tmp_path: Path) -> None:
    run_dir = _write_report(tmp_path, [{"title": "Odd", "severity": "spicy"}])
    (finding,) = strix_report.parse_report(run_dir)
    assert finding.severity is Severity.INFO
    assert finding.title == "Odd"


def test_missing_title_and_description_get_defaults(tmp_path: Path) -> None:
    run_dir = _write_report(tmp_path, [{"severity": "low"}])
    (finding,) = strix_report.parse_report(run_dir)
    assert finding.severity is Severity.LOW
    assert finding.title == "Untitled finding"
    assert finding.description == "No description provided by Strix."
    assert finding.poc_code is None
    assert finding.remediation is None


def test_wrapped_object_shape_is_tolerated(tmp_path: Path) -> None:
    run_dir = _write_report(tmp_path, {"vulnerabilities": [{"title": "x", "severity": "high"}]})
    (finding,) = strix_report.parse_report(run_dir)
    assert finding.severity is Severity.HIGH


def test_malformed_json_raises(tmp_path: Path) -> None:
    run_dir = tmp_path / "strix_runs" / "run-bad"
    run_dir.mkdir(parents=True)
    (run_dir / strix_report.VULNERABILITIES_FILENAME).write_text("{not json", encoding="utf-8")
    try:
        strix_report.parse_report(run_dir)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError on malformed report")
