"""Re-run one finding's proof of concept and decide whether it still works.

This closes the loop the market keeps saying is broken: a finding reappears on
the next scan with no indication of whether anyone fixed it, whether it was
ever exploitable, or what changed. A retest answers exactly one question —
*does this specific exploit still work?* — and records the answer as evidence
attached to the finding, not to the run.

The decision rule is deliberately asymmetric:

* The engine reports the same fingerprint again → ``STILL_VULNERABLE``.
* The engine completed and did not report it → ``FIXED``.
* The engine could not complete → ``INCONCLUSIVE``.

"Could not complete" must never collapse into "fixed". A tool that says fixed
when it means *I did not check* is worse than one that says nothing, and it is
the failure mode that costs a security product its credibility permanently.

Pure and dependency-free so the instruction text and the decision rule can be
unit-tested without a database or an engine.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from app.models.enums import RetestOutcome

# The PoC is the heart of the instruction, but a giant script would crowd out
# everything else in the agent's context.
_MAX_POC_CHARS = 6000
_MAX_DESCRIPTION_CHARS = 2000


def _clip(text: Optional[str], limit: int) -> str:
    if not text:
        return ""
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "\n…[truncated]…"


def build_instruction(
    *,
    title: str,
    fingerprint: str,
    description: Optional[str] = None,
    poc_code: Optional[str] = None,
    file_path: Optional[str] = None,
    target_url: Optional[str] = None,
    remediation: Optional[str] = None,
) -> str:
    """Compose the instruction for a single-finding verification run.

    It asks for one thing and forbids the tempting substitute: do not go
    looking for other problems, and do not declare success because the code
    now *looks* right. Re-run the exploit.
    """
    lines: list[str] = [
        "# Verification retest — one finding only",
        "",
        "You are re-testing a single previously reported vulnerability to "
        "determine whether it has actually been fixed. This is not a new "
        "assessment: do not survey the target for other issues, and do not "
        "report anything else you happen to notice.",
        "",
        f"## Finding under test\nTitle: {title}",
    ]
    if file_path:
        lines.append(f"Location: {file_path}")
    if target_url:
        lines.append(f"Target: {target_url}")

    if description:
        lines += ["", "## Original description", _clip(description, _MAX_DESCRIPTION_CHARS)]
    if poc_code:
        lines += [
            "",
            "## Original proof of concept",
            "Re-run this exploit against the target as-is, adapting it only as "
            "far as necessary to account for changed routes or parameter names.",
            "",
            "```",
            _clip(poc_code, _MAX_POC_CHARS),
            "```",
        ]
    if remediation:
        lines += ["", "## Fix that was recommended", _clip(remediation, 800)]

    lines += [
        "",
        "## What to report",
        "- If the exploit still succeeds, report this vulnerability exactly "
        "once, keeping the same title, and include the request and response "
        "that prove it.",
        "- If the exploit no longer succeeds, report NO vulnerabilities at "
        "all, and state in your summary what you attempted and how the "
        "application responded.",
        "",
        "Judge only by what the application actually does. Source code that "
        "looks corrected is not evidence that the exploit fails, and a fix "
        "elsewhere in the codebase is not evidence about this one.",
    ]
    return "\n".join(lines)


def decide_outcome(
    *,
    completed: bool,
    reported_fingerprints: Iterable[str],
    fingerprint: str,
) -> RetestOutcome:
    """Interpret a retest run.

    ``completed`` is whether the engine finished its work at all — a timeout,
    a crashed sandbox or an unreachable target all mean we learned nothing.
    """
    if not completed:
        return RetestOutcome.INCONCLUSIVE
    if fingerprint in set(reported_fingerprints):
        return RetestOutcome.STILL_VULNERABLE
    return RetestOutcome.FIXED


def build_evidence(
    outcome: RetestOutcome,
    *,
    scan_id: Any,
    finding: Optional[Any] = None,
    engine: Optional[str] = None,
    model: Optional[str] = None,
    target_url: Optional[str] = None,
    commit_sha: Optional[str] = None,
    error: Optional[str] = None,
    observed_at: Optional[datetime] = None,
) -> dict:
    """The receipt for a retest verdict.

    Stored on the triage row so a report can say "we re-ran this exploit on
    this date against this commit and it no longer works" — the sentence a
    customer wants to show their auditor, and the one a bare status field
    cannot support.
    """
    when = (observed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    bundle: dict[str, Any] = {
        "outcome": outcome.value,
        "scan_id": str(scan_id),
        "verified_at": when.isoformat(),
        "engine": engine,
        "model": model,
        "target_url": target_url,
        "commit_sha": commit_sha,
    }

    if outcome is RetestOutcome.STILL_VULNERABLE and finding is not None:
        # Carry the fresh observation across: what the exploit did *this time*
        # is the useful part, not what it did months ago.
        observation = getattr(finding, "evidence", None) or {}
        bundle["request"] = observation.get("request")
        bundle["response"] = observation.get("response")
        bundle["poc_output"] = observation.get("poc_output")
    if outcome is RetestOutcome.INCONCLUSIVE:
        bundle["error"] = error or "The retest did not complete."

    return {k: v for k, v in bundle.items() if v is not None}


def summarize(outcome: Optional[RetestOutcome], when: Optional[datetime]) -> str:
    """One line for a report or a notification."""
    if outcome is None:
        return "Not retested"
    stamp = f" on {when.strftime('%Y-%m-%d')}" if when else ""
    return {
        RetestOutcome.FIXED: f"Verified fixed{stamp} — the exploit no longer works",
        RetestOutcome.STILL_VULNERABLE: f"Still vulnerable{stamp} — the exploit still works",
        RetestOutcome.INCONCLUSIVE: f"Retest inconclusive{stamp} — nothing was proven",
    }[outcome]
