"""Scan-completion notifications (email + the Pro/Enterprise Slack webhook).

Best-effort: a failed or unconfigured channel is logged and swallowed so it
never affects the scan itself. Message building is split from sending so the
payload can be unit-tested without a network call.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Optional

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
    elif status == "canceled":
        headline = f":black_square_for_stop: *{repo_name}* — scan canceled"
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


def notify_scan_finished(
    *,
    email_to: Optional[str],
    slack_webhook_url: Optional[str],
    repo_name: str,
    status: str,
    total: int,
    counts: dict[str, int],
    report_url: str,
) -> None:
    """Fan a finished-scan notice out to every channel the user has enabled.

    Shared by the worker (completed/failed) and the cancel endpoint so the two
    paths can't drift in wording or in which channels they reach. Both
    channels swallow their own delivery errors; notifying is never worth
    failing the caller for.
    """
    # Imported here, not at module scope: app.services.email imports
    # ``severity_breakdown`` from this module, so a top-level import cycles.
    from app.services import email as email_service

    if email_to:
        try:
            email_service.send_scan_complete_email(
                email_to,
                repo_name=repo_name,
                status=status,
                total=total,
                counts=counts,
                report_url=report_url,
            )
        except Exception:  # noqa: BLE001 - delivery must not break the caller
            logger.exception("Failed to send scan email for %s", repo_name)

    if slack_webhook_url:
        notify_scan_complete(
            slack_webhook_url,
            repo_name=repo_name,
            status=status,
            total=total,
            counts=counts,
            report_url=report_url,
        )


# --- Generic outbound webhook --------------------------------------------
# One signed POST per finished scan. This is deliberately a single generic
# hook rather than N first-party integrations: Jira, Linear, PagerDuty and
# SIEM pipelines all accept an HTTP POST (directly or via a connector), so one
# well-specified payload covers them without Aegis maintaining each API.

SIGNATURE_HEADER = "X-Aegis-Signature"
TIMESTAMP_HEADER = "X-Aegis-Timestamp"
EVENT_HEADER = "X-Aegis-Event"

_SIGNATURE_VERSION = "sha256"


def build_scan_event(
    *,
    event: str,
    scan_id: str,
    repo_name: str,
    status: str,
    total: int,
    counts: dict[str, int],
    report_url: str,
) -> dict:
    """The JSON body delivered to a user's webhook for a finished scan."""
    return {
        "event": event,
        "scan": {
            "id": scan_id,
            "repository": repo_name,
            "status": status,
            "report_url": report_url,
        },
        "findings": {
            "total": total,
            # Always all five keys so a consumer can index without branching.
            "by_severity": {
                sev: counts.get(sev, 0)
                for sev in ("critical", "high", "medium", "low", "info")
            },
        },
    }


def sign_payload(secret: str, timestamp: str, body: bytes) -> str:
    """HMAC-SHA256 over ``timestamp.body``, as ``sha256=<hex>``.

    The timestamp is inside the signed material (rather than only a header) so
    a captured delivery cannot be replayed with a fresh timestamp — the
    receiver rejects a stale one and the signature can't be recomputed
    without the secret.
    """
    material = timestamp.encode("utf-8") + b"." + body
    digest = hmac.new(secret.encode("utf-8"), material, hashlib.sha256).hexdigest()
    return f"{_SIGNATURE_VERSION}={digest}"


def notify_webhook(
    webhook_url: str,
    secret: Optional[str],
    *,
    event: str = "scan.completed",
    scan_id: str,
    repo_name: str,
    status: str,
    total: int,
    counts: dict[str, int],
    report_url: str,
) -> None:
    """POST the scan result to the user's webhook. Never raises.

    Signed when a secret is configured; unsigned otherwise, since a receiver
    that doesn't verify shouldn't be forced to hold a secret.
    """
    if not webhook_url:
        return

    payload = build_scan_event(
        event=event,
        scan_id=scan_id,
        repo_name=repo_name,
        status=status,
        total=total,
        counts=counts,
        report_url=report_url,
    )
    # Serialize once: the bytes that are signed must be the bytes that are sent.
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        EVENT_HEADER: event,
    }
    if secret:
        timestamp = str(int(time.time()))
        headers[TIMESTAMP_HEADER] = timestamp
        headers[SIGNATURE_HEADER] = sign_payload(secret, timestamp, body)

    try:
        resp = httpx.post(
            webhook_url, content=body, headers=headers, timeout=_TIMEOUT_SECONDS
        )
        resp.raise_for_status()
    except Exception:  # noqa: BLE001 - notifications must not break the scan
        logger.exception("Failed to deliver webhook for %s", repo_name)
