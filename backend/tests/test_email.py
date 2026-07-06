"""Scan-complete email construction (no SMTP; send is monkeypatched)."""
from __future__ import annotations

from app.services import email


def _capture(monkeypatch):
    sent = {}

    def fake_send(to, subject, text, html=None):
        sent.update(to=to, subject=subject, text=text, html=html)

    monkeypatch.setattr(email, "send_email", fake_send)
    return sent


def test_clean_scan_email(monkeypatch):
    sent = _capture(monkeypatch)
    email.send_scan_complete_email(
        "u@x.com", repo_name="acme/api", status="completed", total=0,
        counts={}, report_url="https://app/scans/1",
    )
    assert sent["to"] == "u@x.com"
    assert "all clear" in sent["subject"]
    assert "https://app/scans/1" in sent["text"]


def test_findings_scan_email(monkeypatch):
    sent = _capture(monkeypatch)
    email.send_scan_complete_email(
        "u@x.com", repo_name="acme/api", status="completed", total=3,
        counts={"critical": 1, "high": 2}, report_url="https://app/scans/1",
    )
    assert "3 vulnerabilities" in sent["subject"]
    assert "1 critical, 2 high" in sent["text"]


def test_failed_scan_email(monkeypatch):
    sent = _capture(monkeypatch)
    email.send_scan_complete_email(
        "u@x.com", repo_name="acme/api", status="failed", total=0,
        counts={}, report_url="https://app/scans/1",
    )
    assert "failed" in sent["subject"]
