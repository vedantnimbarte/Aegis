"""Decide whether a pull request should be blocked.

The rule that makes a security gate survivable: **only new findings block.**
A team that turns on scanning inherits whatever their codebase already had,
and a check that fails on that backlog gets switched off in week two — which
costs more security than it ever bought. Pre-existing findings are still
reported in the comment; they just do not fail the build.

Policy is per target (``gate_fail_severities``, ``gate_new_findings_only``)
with the platform default behind it, so one noisy legacy service can be set to
warn-only without weakening the gate everywhere else.

Pure and dependency-free apart from settings, so the decision can be
unit-tested without a database or GitHub.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from app.core.config import settings

_SEVERITY_ORDER = ("critical", "high", "medium", "low", "info")


def default_fail_severities() -> set[str]:
    return {
        s.strip().lower()
        for s in settings.GITHUB_CHECK_FAIL_SEVERITIES.split(",")
        if s.strip()
    }


def fail_severities_for(target: Optional[Any]) -> set[str]:
    """Blocking severities for a target, falling back to the platform default.

    An explicitly empty policy string means "never block", which is a real
    choice a team makes for a legacy service — so it is honoured rather than
    treated as unset.
    """
    if target is None:
        return default_fail_severities()
    raw = getattr(target, "gate_fail_severities", None)
    if raw is None:
        return default_fail_severities()
    return {s.strip().lower() for s in raw.split(",") if s.strip()}


def _severity_of(finding: Any) -> str:
    value = getattr(finding, "severity", "info")
    return str(getattr(value, "value", value)).lower()


def counts_of(findings: Iterable[Any]) -> dict[str, int]:
    counts = {sev: 0 for sev in _SEVERITY_ORDER}
    for finding in findings:
        sev = _severity_of(finding)
        counts[sev] = counts.get(sev, 0) + 1
    return counts


@dataclass(frozen=True)
class GateDecision:
    """The verdict, plus the numbers that justify it."""

    conclusion: str            # "success" | "failure"
    blocking_count: int
    new_count: int
    total_count: int
    new_findings_only: bool
    has_baseline: bool

    @property
    def blocked(self) -> bool:
        return self.conclusion == "failure"

    def summary(self) -> str:
        """One line explaining the verdict — the part a developer reads."""
        if self.total_count == 0:
            return "No exploitable vulnerabilities found."
        if not self.blocked:
            if self.new_findings_only and self.has_baseline and self.total_count:
                return (
                    f"No new blocking findings. {self.total_count} pre-existing "
                    "finding(s) reported but not blocking this pull request."
                )
            return f"{self.total_count} finding(s) reported, none at a blocking severity."
        scope = "new " if self.new_findings_only and self.has_baseline else ""
        return (
            f"{self.blocking_count} {scope}finding(s) at a blocking severity. "
            "Resolve them or adjust this target's gate policy to merge."
        )


def decide(
    findings: Iterable[Any],
    *,
    target: Optional[Any] = None,
    new_fingerprints: Optional[set[str]] = None,
    has_baseline: bool = False,
) -> GateDecision:
    """Block or pass a pull request.

    ``new_fingerprints`` comes from the scan diff. With no baseline to compare
    against — the target's first scan — everything is treated as new, because
    on a first run there is no backlog to grandfather in yet.
    """
    findings = list(findings)
    blocking_severities = fail_severities_for(target)
    new_only = bool(getattr(target, "gate_new_findings_only", True)) if target else True

    if new_only and has_baseline:
        fingerprints = new_fingerprints or set()
        considered = [
            f for f in findings if getattr(f, "fingerprint", None) in fingerprints
        ]
    else:
        considered = findings

    blocking = [f for f in considered if _severity_of(f) in blocking_severities]
    return GateDecision(
        conclusion="failure" if blocking else "success",
        blocking_count=len(blocking),
        new_count=len(considered) if (new_only and has_baseline) else len(findings),
        total_count=len(findings),
        new_findings_only=new_only,
        has_baseline=has_baseline,
    )
