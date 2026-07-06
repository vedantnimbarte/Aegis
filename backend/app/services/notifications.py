"""Slack notifications for scan completion (Pro/Enterprise integration).

Best-effort: a failed or unconfigured webhook is logged and swallowed so it
never affects the scan itself. Message building is split from sending so the
payload can be unit-tested without a network call.
"""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("aegis.notifications")

_TIMEOUT_SECONDS = 10


def severity_breakdown(counts: dict[str, int]) -> str:
    """Non-zero severities in priority order, e.g. ``"1 critical, 2 high"``."""
    return ", ".join(
        f"{counts.get(sev, 0)} {sev}"
        for sev in ("critical", "high", "medium", "low")
        if counts.get(sev, 0)
    )


def build_scan_message(
    *,
    repo_name: str,
    status: str,
    total: int,
    counts: dict[str, int],
    report_url: str,
) -> dict:
    """Build a Slack incoming-webhook payload for a finished scan."""
    if status == "completed":
        if total == 0:
            headline = f":white_check_mark: *{repo_name}* — no vulnerabilities found"
        else:
            headline = (
                f":rotating_light: *{repo_name}* — {total} "
                f"vulnerabilit{'y' if total == 1 else 'ies'} "
                f"({severity_breakdown(counts)})"
            )
    else:
        headline = f":x: *{repo_name}* — scan failed"

    return {
        "text": f"{headline}\n<{report_url}|View report>",
    }


def notify_scan_complete(
    webhook_url: str,
    *,
    repo_name: str,
    status: str,
    total: int,
    counts: dict[str, int],
    report_url: str,
) -> None:
    """POST the scan result to a Slack webhook. Never raises."""
    if not webhook_url:
        return
    payload = build_scan_message(
        repo_name=repo_name,
        status=status,
        total=total,
        counts=counts,
        report_url=report_url,
    )
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except Exception:  # noqa: BLE001 - notifications must not break the scan
        logger.exception("Failed to post Slack notification for %s", repo_name)
