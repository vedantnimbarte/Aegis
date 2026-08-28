"""Build the evidence bundle stored alongside every finding.

The single most common complaint about AI pentesting is findings nobody can
reproduce: a convincing description of an exploit that never existed. One
caught hallucination costs a tool the benefit of the doubt on everything else
it reports, so the answer cannot be a better description — it has to be the
receipt. This module assembles it:

    what was sent, what came back, what the PoC printed, against which URL and
    which commit, produced by which engine and model, at what time.

Three rules shape the code:

* **Never invent.** A field the engine did not record is absent, not
  plausible-looking filler. A partial bundle is honest; a complete-looking
  fabricated one is the disease.
* **Redact.** Transcripts are captured from live traffic and routinely carry
  the tester's session cookie or bearer token. Those are stripped before the
  bundle is stored, because a report gets shared with auditors and prospects.
* **Bound the size.** A response body can be megabytes. Evidence lives in a
  JSONB column read on every report render, so each field is truncated.

Pure and dependency-free (no DB, no settings) so it can be unit-tested
directly, matching ``strix_report`` and ``finding_identity``.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

# Per-field ceiling. Enough to hold a full request and a useful slice of a
# response without turning the report query into a bulk download.
MAX_FIELD_CHARS = 8000
_ELISION = "\n…[truncated]…"

# Header lines and JSON/form fields whose values are credentials. Matched
# case-insensitively against a transcript before it is persisted.
_SECRET_HEADERS = (
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
    "api-key",
)
_HEADER_PATTERN = re.compile(
    r"^(?P<name>" + "|".join(_SECRET_HEADERS) + r")\s*:\s*(?P<value>.+)$",
    re.IGNORECASE | re.MULTILINE,
)
# "password": "hunter2"  /  password=hunter2  — both shapes appear in bodies.
_BODY_SECRET_PATTERN = re.compile(
    r"(?P<key>\"?(?:password|passwd|secret|token|api_key|apikey|access_token|"
    r"refresh_token|client_secret)\"?\s*[:=]\s*)"
    r"(?P<value>\"[^\"]*\"|[^\s,&}]+)",
    re.IGNORECASE,
)

REDACTED = "[redacted]"


def redact(text: Optional[str]) -> Optional[str]:
    """Strip credentials from a transcript, keeping its shape readable.

    The header name and the field name survive — knowing that a request
    carried an ``Authorization`` header is part of understanding the finding.
    Only the value goes.
    """
    if not text:
        return None
    cleaned = _HEADER_PATTERN.sub(lambda m: f"{m.group('name')}: {REDACTED}", text)
    cleaned = _BODY_SECRET_PATTERN.sub(lambda m: f"{m.group('key')}{REDACTED}", cleaned)
    return cleaned


def truncate(text: Optional[str], limit: int = MAX_FIELD_CHARS) -> Optional[str]:
    """Trim to ``limit``, keeping both ends.

    Head-only truncation loses the outcome: an HTTP transcript's status and a
    PoC's verdict are at the end, so cutting the tail leaves proof of nothing.
    """
    if text is None:
        return None
    if len(text) <= limit:
        return text
    budget = limit - len(_ELISION)
    head = (budget * 2) // 3
    return text[:head] + _ELISION + text[-(budget - head):]


def _clean(text: Optional[str]) -> Optional[str]:
    return truncate(redact(text))


def build(
    raw: Optional[dict],
    *,
    engine: Optional[str] = None,
    model: Optional[str] = None,
    target_url: Optional[str] = None,
    commit_sha: Optional[str] = None,
    observed_at: Optional[datetime] = None,
) -> Optional[dict]:
    """Assemble the stored bundle from what the engine recorded plus run context.

    Returns None when there is nothing to show. An evidence key present but
    empty would make the UI promise proof it cannot display.
    """
    raw = raw or {}
    observed = observed_at or datetime.now(timezone.utc)

    bundle: dict[str, Any] = {
        "request": _clean(raw.get("request")),
        "response": _clean(raw.get("response")),
        "poc_output": _clean(raw.get("poc_output")),
        "notes": _clean(raw.get("notes")),
        # The engine's own endpoint wins: it is where the exploit actually
        # landed, which may be more specific than the target we were given.
        "target_url": raw.get("target_url") or target_url,
        "method": raw.get("method"),
        "commit_sha": commit_sha,
        "engine": engine,
        "model": model,
        "observed_at": observed.astimezone(timezone.utc).isoformat(),
    }
    populated = {k: v for k, v in bundle.items() if v}

    # Provenance alone is not evidence. Unless something was actually
    # observed, storing a bundle would dress up "we ran at 10:04" as proof.
    if not any(populated.get(k) for k in ("request", "response", "poc_output", "notes")):
        return None
    return populated


def has_proof(bundle: Optional[dict]) -> bool:
    """Whether a bundle contains an observation, not just run metadata."""
    if not bundle:
        return False
    return any(bundle.get(k) for k in ("request", "response", "poc_output"))


def summarize(bundle: Optional[dict]) -> str:
    """One line naming what proof exists — for a PDF or a list row."""
    if not bundle:
        return "No evidence captured"
    present = [
        label
        for key, label in (
            ("request", "request"),
            ("response", "response"),
            ("poc_output", "PoC output"),
            ("notes", "tester notes"),
        )
        if bundle.get(key)
    ]
    if not present:
        return "No evidence captured"
    return "Captured: " + ", ".join(present)
