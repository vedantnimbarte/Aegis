"""The compliance pack: the document an auditor and a prospect will accept.

A findings list is not a pentest report. What unblocks an enterprise deal or
satisfies a SOC 2 auditor is a document that states *what was in scope*, *how
it was tested*, *when*, *what was found*, *what was fixed and how that was
verified*, and carries an attestation from the party that performed the test.
Aegis produces every one of those facts already; this module assembles them
into the shape the reader expects.

Two honesty rules, because a compliance document that overstates is worse than
none at all:

* The methodology says plainly that testing was performed by an autonomous
  agent, with a named human attestor. Auditors ask; a report that obscures it
  fails the question badly.
* Control mappings are described as *evidence toward* a control, never as a
  pass. No tool can certify SOC 2, and claiming to is how a customer gets
  burned in an audit they trusted us for.

Pure and dependency-free: it reads the report by duck typing and returns
plain data, so ``report_pdf`` renders it and tests exercise it directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

# --- Control mappings -----------------------------------------------------
# What a scan of this kind is evidence *toward*. Wording is deliberately
# "evidence toward", never "compliant with".
@dataclass(frozen=True)
class ControlMapping:
    framework: str
    control: str
    description: str


CONTROL_MAPPINGS: tuple[ControlMapping, ...] = (
    ControlMapping(
        "SOC 2 (TSC 2017)",
        "CC4.1",
        "Ongoing evaluation of internal control: recurring automated testing "
        "with recorded results and remediation tracking.",
    ),
    ControlMapping(
        "SOC 2 (TSC 2017)",
        "CC7.1",
        "Detection of vulnerabilities: monitoring of the application for new "
        "vulnerabilities introduced by change.",
    ),
    ControlMapping(
        "SOC 2 (TSC 2017)",
        "CC7.2",
        "Analysis of anomalies: validated findings with proof of exploitation "
        "rather than unverified alerts.",
    ),
    ControlMapping(
        "ISO/IEC 27001:2022",
        "A.8.8",
        "Management of technical vulnerabilities: identification, evaluation "
        "and remediation of vulnerabilities in the tested systems.",
    ),
    ControlMapping(
        "ISO/IEC 27001:2022",
        "A.8.29",
        "Security testing in development and acceptance: testing performed "
        "against the application before and after change.",
    ),
    ControlMapping(
        "PCI DSS v4.0",
        "11.4",
        "External and internal penetration testing of the in-scope application "
        "layer, with findings retested after correction.",
    ),
    ControlMapping(
        "OWASP ASVS 4.0",
        "V1–V13",
        "Application security verification across authentication, access "
        "control, input handling, and business logic.",
    ),
)

METHODOLOGY_STEPS: tuple[tuple[str, str], ...] = (
    (
        "Reconnaissance",
        "The target is enumerated to build a map of its routes, parameters, "
        "authentication flows and, for source-connected targets, its code "
        "structure.",
    ),
    (
        "Vulnerability identification",
        "Autonomous agents analyse that map for weaknesses across the OWASP "
        "Top 10 classes, access-control and business-logic flaws, and — where "
        "applicable — the OWASP GenAI lists for AI-backed features.",
    ),
    (
        "Exploitation and validation",
        "Each candidate weakness is exploited against the running target. A "
        "candidate that cannot be exploited is discarded rather than reported, "
        "which is what distinguishes these findings from a scanner's alerts.",
    ),
    (
        "Evidence capture",
        "For every confirmed finding the request, the response and the proof-of-"
        "concept output are recorded, with the target and commit under test.",
    ),
    (
        "Remediation guidance",
        "Each finding carries a specific fix. Where the fix is a code change, "
        "it is provided as a concrete patch.",
    ),
    (
        "Verification retesting",
        "After remediation, the original proof of concept is re-run against the "
        "target. A finding is recorded as fixed only when the exploit no longer "
        "succeeds.",
    ),
)

LIMITATIONS = (
    "Testing was performed by autonomous software agents under human-defined "
    "scope and authorization. It is not equivalent to a manual engagement by a "
    "human penetration-testing team and does not carry an individual tester's "
    "professional certification.",
    "Coverage is limited to the targets listed in the scope section, over the "
    "testing window stated. Systems, environments and code paths outside that "
    "scope were not examined.",
    "The absence of a finding is not proof that a vulnerability does not exist. "
    "This report describes what was found and validated, not everything that "
    "could exist.",
    "This document is evidence toward the controls listed. It is not a "
    "certification of compliance with any framework, which only an accredited "
    "auditor can issue.",
)


@dataclass
class ComplianceContext:
    """Everything the pack states that the findings themselves do not."""

    organization_name: str
    target_name: str
    target_kind: str
    scope_description: str
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    engine: str = "Aegis (Strix autonomous agents)"
    model: Optional[str] = None
    vendor_name: str = "Aegis Security"
    attestor_name: str = ""
    attestor_title: str = ""
    report_id: str = ""
    findings_total: int = 0
    open_count: int = 0
    verified_fixed_count: int = 0
    counts_by_severity: dict[str, int] = field(default_factory=dict)


def _fmt(value: Optional[datetime]) -> str:
    if value is None:
        return "not recorded"
    return value.astimezone(timezone.utc).strftime("%d %B %Y, %H:%M UTC")


def build_context(report: Any, *, organization_name: str, **overrides: Any) -> ComplianceContext:
    """Derive the pack's front matter from a rendered report."""
    scan = report.scan
    kind = str(getattr(getattr(scan, "target_kind", None), "value", "") or "target")
    name = getattr(scan, "target_name", None) or "the target"

    context = ComplianceContext(
        organization_name=organization_name,
        target_name=name,
        target_kind=kind,
        scope_description=scope_statement(kind, name),
        window_start=getattr(scan, "started_at", None) or getattr(scan, "created_at", None),
        window_end=getattr(scan, "completed_at", None),
        model=getattr(scan, "engine_model", None),
        report_id=str(getattr(scan, "id", "")),
        findings_total=getattr(report, "total", 0),
        open_count=getattr(report, "open_count", 0),
        verified_fixed_count=getattr(report, "verified_fixed_count", 0),
        counts_by_severity=dict(getattr(report, "counts_by_severity", {}) or {}),
    )
    for key, value in overrides.items():
        if value:
            setattr(context, key, value)
    return context


def scope_statement(kind: str, name: str) -> str:
    """What was in scope, in the words the reader's auditor uses."""
    return {
        "repo": (
            f"The source repository {name}, including its application code and "
            "configuration as present at the commit under test."
        ),
        "web": f"The web application reachable at {name}, and the routes it exposes.",
        "api": f"The HTTP API at {name}, and the endpoints described or discovered for it.",
        "llm": (
            f"The LLM-backed application endpoint at {name}, including its prompt "
            "handling, tool access, and output handling."
        ),
        "mcp": (
            f"The Model Context Protocol server at {name}, including the tools, "
            "resources and prompts it exposes."
        ),
    }.get(kind, f"The target {name}.")


def executive_summary(context: ComplianceContext) -> str:
    """The paragraph a non-technical reader will actually read."""
    counts = context.counts_by_severity or {}
    serious = counts.get("critical", 0) + counts.get("high", 0)

    if context.findings_total == 0:
        outcome = (
            "No exploitable vulnerabilities were identified during this "
            "assessment."
        )
    elif serious:
        outcome = (
            f"{context.findings_total} validated finding(s) were identified, of "
            f"which {serious} are of critical or high severity and require "
            "prompt remediation."
        )
    else:
        outcome = (
            f"{context.findings_total} validated finding(s) were identified. "
            "None are of critical or high severity."
        )

    verified = (
        f" {context.verified_fixed_count} finding(s) have since been remediated "
        "and verified by re-running the original proof of concept."
        if context.verified_fixed_count
        else ""
    )
    return (
        f"{context.vendor_name} performed an automated penetration test of "
        f"{context.scope_description[0].lower()}{context.scope_description[1:]} "
        f"between {_fmt(context.window_start)} and {_fmt(context.window_end)}. "
        f"{outcome}{verified} Every finding in this report was validated by "
        "exploitation; unexploitable candidates were discarded rather than "
        "reported."
    )


def attestation_letter(context: ComplianceContext) -> str:
    """The signed statement an auditor accepts in place of the full report.

    Deliberately short and factual. It states who tested what, when, and what
    the outcome was — and nothing about compliance status, which is not ours
    to assert.
    """
    signer = context.attestor_name or f"{context.vendor_name} Security Team"
    title = context.attestor_title or "Security Assurance"
    counts = context.counts_by_severity or {}
    serious = counts.get("critical", 0) + counts.get("high", 0)

    outstanding = (
        f"As at the date of this letter, {context.open_count} finding(s) remain "
        f"open, of which {serious} are critical or high severity."
        if context.open_count
        else "As at the date of this letter, no findings remain open."
    )

    return "\n\n".join(
        [
            "To whom it may concern,",
            (
                f"This letter confirms that {context.vendor_name} performed a "
                f"penetration test of {context.scope_description} on behalf of "
                f"{context.organization_name}."
            ),
            (
                f"Testing was conducted between {_fmt(context.window_start)} and "
                f"{_fmt(context.window_end)} using {context.engine}"
                + (f" ({context.model})" if context.model else "")
                + ". Testing was performed by autonomous agents operating under "
                "an authorization attestation provided by the client, and every "
                "reported finding was confirmed by successful exploitation "
                "against the target."
            ),
            (
                f"A total of {context.findings_total} validated finding(s) were "
                f"reported. {outstanding}"
                + (
                    f" {context.verified_fixed_count} finding(s) have been "
                    "remediated by the client and verified by re-executing the "
                    "original proof of concept."
                    if context.verified_fixed_count
                    else ""
                )
            ),
            (
                "The full technical report, including reproduction steps and "
                "captured evidence for each finding, is available from "
                f"{context.organization_name} on request. This letter attests to "
                "the performance and outcome of the test described above; it is "
                "not a certification of compliance with any framework."
            ),
            f"Report reference: {context.report_id}",
            f"{signer}\n{title}\n{context.vendor_name}",
        ]
    )


def mappings_for(frameworks: Optional[tuple[str, ...]] = None) -> list[ControlMapping]:
    """Control mappings, optionally filtered to the frameworks the reader cares about."""
    if not frameworks:
        return list(CONTROL_MAPPINGS)
    wanted = {f.lower() for f in frameworks}
    return [m for m in CONTROL_MAPPINGS if m.framework.lower() in wanted]
