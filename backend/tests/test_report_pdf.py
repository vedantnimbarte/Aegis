"""Tests for the PDF report renderer (services/report_pdf.py).

Uses duck-typed SimpleNamespace stand-ins for the report so no DB is needed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import report_pdf


def _scan(**kw):
    base = dict(
        scan_mode="deep",
        status="completed",
        started_at=datetime(2026, 7, 6, 10, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 7, 6, 10, 42, tzinfo=timezone.utc),
        created_at=datetime(2026, 7, 6, 9, 59, tzinfo=timezone.utc),
        id="3f1c9a20-0000-4000-8000-000000000001",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _vuln(**kw):
    base = dict(
        severity="high",
        title="Untitled",
        description="",
        poc_code=None,
        remediation=None,
        owasp_category=None,
        cvss_score=None,
        file_path=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_full_report_is_valid_pdf() -> None:
    report = SimpleNamespace(
        scan=_scan(),
        total=2,
        counts_by_severity={"critical": 1, "high": 1, "medium": 0, "low": 0, "info": 0},
        vulnerabilities=[
            _vuln(
                severity="critical",
                title="SQL Injection in /login — takeover",  # em dash exercises _s
                description="User ’input’ hits the query → boom. Bullet: • x",
                poc_code='curl -d "u=\' OR 1=1--" https://x/login',
                remediation="Use parameterized queries.",
                owasp_category="CWE-89",
                cvss_score=9.8,
                file_path="app/auth.py:42-45",
            ),
            _vuln(severity="high", title="Missing rate limiting", description="No throttling."),
        ],
    )
    pdf = report_pdf.build_report_pdf(report, "acme/payments-api")
    assert isinstance(pdf, (bytes, bytearray))
    assert bytes(pdf[:5]) == b"%PDF-"
    assert len(pdf) > 1500


def test_empty_report_is_valid_pdf() -> None:
    report = SimpleNamespace(
        scan=_scan(),
        total=0,
        counts_by_severity={"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        vulnerabilities=[],
    )
    pdf = report_pdf.build_report_pdf(report, "acme/clean-repo")
    assert bytes(pdf[:5]) == b"%PDF-"


def test_enum_like_severity_and_paging() -> None:
    """Severity given as an enum-like object, plus enough findings to paginate."""
    report = SimpleNamespace(
        scan=_scan(),
        total=12,
        counts_by_severity={"critical": 0, "high": 12, "medium": 0, "low": 0, "info": 0},
        vulnerabilities=[
            _vuln(
                severity=SimpleNamespace(value="high"),
                title=f"Finding {i}",
                description="lorem ipsum " * 40,
                poc_code="print('x')\n" * 6,
                remediation="Fix. " * 20,
            )
            for i in range(12)
        ],
    )
    pdf = report_pdf.build_report_pdf(report, "acme/big-repo")
    assert bytes(pdf[:5]) == b"%PDF-"


def test_sanitizer_replaces_non_latin1() -> None:
    # Smart punctuation / arrows / bullets are normalized to ASCII.
    assert report_pdf._s("’ “ ” — → •") == "' \" \" - -> -"
    # Characters outside Latin-1 (e.g. CJK) fall back to '?'.
    assert report_pdf._s("中文") == "??"
    assert report_pdf._s(None) == ""
