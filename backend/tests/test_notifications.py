"""Slack notification payload building (pure, no network)."""
from __future__ import annotations

from app.services import notifications


def test_clean_scan_message():
    msg = notifications.build_scan_message(
        repo_name="acme/api", status="completed", total=0, counts={},
        report_url="https://app/scans/1",
    )
    assert "no vulnerabilities" in msg["text"]
    assert "https://app/scans/1" in msg["text"]


def test_findings_message_lists_severities():
    msg = notifications.build_scan_message(
        repo_name="acme/api", status="completed", total=3,
        counts={"critical": 1, "high": 2, "medium": 0, "low": 0},
        report_url="https://app/scans/1",
    )
    text = msg["text"]
    assert "3 vulnerabilities" in text
    assert "1 critical" in text and "2 high" in text
    # Zero-count severities are omitted.
    assert "medium" not in text


def test_failed_message():
    msg = notifications.build_scan_message(
        repo_name="acme/api", status="failed", total=0, counts={},
        report_url="https://app/scans/1",
    )
    assert "failed" in msg["text"]


def test_notify_noop_without_webhook():
    # Empty webhook must not attempt any network call (would raise otherwise).
    notifications.notify_scan_complete(
        "", repo_name="x", status="completed", total=0, counts={}, report_url="u"
    )
