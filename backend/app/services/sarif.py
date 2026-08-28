"""Render a scan report as SARIF 2.1.0.

SARIF is what GitHub code scanning ingests, so exporting it puts Aegis
findings in the repository's Security tab alongside CodeQL — no dashboard
visit required. The mapping is deliberately lossy in one direction only: every
SARIF consumer gets severity, location and remediation, while the PoC and the
full description stay in the Aegis report.

Two details make this worth more than a format conversion:

* Triage carries over. A finding marked false-positive or accepted-risk in
  Aegis is emitted with a SARIF ``suppressions`` entry, so GitHub hides it
  too instead of re-raising an alert someone already dismissed.
* Identity carries over. ``partialFingerprints`` uses the same fingerprint
  that backs triage and the scan diff, so GitHub tracks an alert as one issue
  across re-scans rather than closing and reopening it.

Pure and dependency-free — it reads the report via duck typing so a
``SimpleNamespace`` stand-in works in tests, mirroring ``report_pdf``.
"""
from __future__ import annotations

from typing import Any, Iterable

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

_TOOL_NAME = "Aegis"
_TOOL_URI = "https://github.com/usestrix/strix"

# SARIF has three result levels; five severities have to fold into them.
_LEVEL_BY_SEVERITY = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}

# GitHub reads `security-severity` (a CVSS-style number) to bucket alerts into
# its own Critical/High/Medium/Low. Used only when a finding has no CVSS score.
_FALLBACK_SECURITY_SEVERITY = {
    "critical": "9.5",
    "high": "7.5",
    "medium": "5.0",
    "low": "3.0",
    "info": "0.0",
}

# Verdicts that mean a human decided this needs no action. Kept in sync with
# triage_service.SUPPRESSED_STATUSES, but spelled as strings because the
# report carries triage_status as a plain value.
_SUPPRESSED = frozenset({"false_positive", "accepted_risk", "fixed"})


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _rule_id(finding: Any) -> str:
    """A stable rule id for grouping.

    The fingerprint already encodes title + file + classification, so it is the
    natural per-issue rule id. Findings ingested before fingerprinting fall
    back to their OWASP category, then to a generic bucket.
    """
    fingerprint = getattr(finding, "fingerprint", None)
    if fingerprint:
        return f"aegis/{fingerprint[:16]}"
    category = getattr(finding, "owasp_category", None)
    if category:
        return f"aegis/{_text(category).strip().lower().replace(' ', '-')}"
    return "aegis/finding"


def _security_severity(finding: Any, severity: str) -> str:
    score = getattr(finding, "cvss_score", None)
    if score is not None:
        return f"{float(score):.1f}"
    return _FALLBACK_SECURITY_SEVERITY.get(severity, "0.0")


def _severity_of(finding: Any) -> str:
    """The finding's severity as a lowercase string, enum or not."""
    severity = getattr(finding, "severity", None)
    return _text(getattr(severity, "value", severity)).lower()


def _build_rule(finding: Any, severity: str) -> dict:
    """A SARIF reportingDescriptor describing one class of finding."""
    title = _text(getattr(finding, "title", None)) or "Finding"
    remediation = _text(getattr(finding, "remediation", None))
    description = _text(getattr(finding, "description", None))

    rule: dict[str, Any] = {
        "id": _rule_id(finding),
        "name": title,
        "shortDescription": {"text": title},
        "fullDescription": {"text": description or title},
        "defaultConfiguration": {"level": _LEVEL_BY_SEVERITY.get(severity, "warning")},
        "properties": {
            "security-severity": _security_severity(finding, severity),
            # GitHub renders these as filter chips on the alert list.
            "tags": [t for t in ("security", getattr(finding, "owasp_category", None)) if t],
        },
    }
    if remediation:
        # Shown as the "Recommendation" panel on a GitHub alert.
        rule["help"] = {
            "text": remediation,
            "markdown": f"**Remediation**\n\n{remediation}",
        }
    return rule


def _build_result(finding: Any, severity: str) -> dict:
    """A SARIF result — one occurrence of a rule at a location."""
    title = _text(getattr(finding, "title", None)) or "Finding"
    description = _text(getattr(finding, "description", None))
    file_path = _text(getattr(finding, "file_path", None))

    result: dict[str, Any] = {
        "ruleId": _rule_id(finding),
        "level": _LEVEL_BY_SEVERITY.get(severity, "warning"),
        "message": {"text": description or title},
    }

    # A location is required for GitHub to attach the alert to code. Findings
    # with no file (a live-target/DAST result) are anchored on the repository
    # root so they still surface rather than being dropped on ingest.
    result["locations"] = [
        {
            "physicalLocation": {
                "artifactLocation": {"uri": file_path or "."},
            }
        }
    ]

    fingerprint = getattr(finding, "fingerprint", None)
    if fingerprint:
        # Lets GitHub follow one alert across re-scans instead of churning it.
        result["partialFingerprints"] = {"aegisFingerprint/v1": fingerprint}

    status = _text(getattr(finding, "triage_status", "open")) or "open"
    if status in _SUPPRESSED:
        note = _text(getattr(finding, "triage_note", None))
        suppression: dict[str, Any] = {"kind": "external", "status": "accepted"}
        if note:
            suppression["justification"] = note
        result["suppressions"] = [suppression]

    return result


def build_sarif(report: Any, repo_name: str) -> dict:
    """Convert a ``ScanReport`` into a SARIF 2.1.0 log document.

    Rules are de-duplicated by id: several findings of the same class collapse
    to one rule with several results, which is how SARIF expects to be read.
    """
    findings: Iterable[Any] = getattr(report, "vulnerabilities", []) or []

    rules: dict[str, dict] = {}
    results: list[dict] = []

    for finding in findings:
        severity = _severity_of(finding)
        rule = _build_rule(finding, severity)
        rules.setdefault(rule["id"], rule)
        results.append(_build_result(finding, severity))

    scan = getattr(report, "scan", None)
    scan_id = _text(getattr(scan, "id", None))

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": _TOOL_NAME,
                        "informationUri": _TOOL_URI,
                        "rules": list(rules.values()),
                    }
                },
                "properties": {
                    "repository": repo_name,
                    "scanId": scan_id,
                },
                "results": results,
            }
        ],
    }
