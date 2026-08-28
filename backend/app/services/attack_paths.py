"""Compose individual findings into attack chains.

A scanner reports a list. A pentester reports a path: *this* leaked internal
hostname plus *that* unauthenticated admin route is not two mediums, it is one
critical. Chaining is the part of a manual engagement automated tools drop, and
it is the argument against the cheap SAST tool sitting next to us in the
buyer's stack.

How it works: each finding is tagged with the capability it grants an attacker
(a foothold, a credential, a way to reach something internal), inferred from
its title and CWE. A rule fires when the capabilities it needs are all present
on the same asset, and produces a chain whose severity is one step above the
worst link — because composition is what makes it worse.

Deliberately conservative. A false chain is worse than a missed one: it
inflates severity, and severity inflation is how a report stops being read. So
rules require an explicit capability match, findings must share an asset, and
anything ambiguous simply produces no chain.

Pure and dependency-free — findings are read by duck typing, so tests pass
``SimpleNamespace`` objects like the other report modules do.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from app.models.enums import Severity

# Severity ordering, worst first — shared with the report renderers.
_SEVERITY_ORDER = [
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.INFO,
]


def _escalate(severity: Severity) -> Severity:
    """One step worse, saturating at critical."""
    index = _SEVERITY_ORDER.index(severity)
    return _SEVERITY_ORDER[max(0, index - 1)]


def _worst(severities: Iterable[Severity]) -> Severity:
    worst = Severity.INFO
    for severity in severities:
        if _SEVERITY_ORDER.index(severity) < _SEVERITY_ORDER.index(worst):
            worst = severity
    return worst


# --- Capabilities ---------------------------------------------------------
# What a finding gives an attacker, rather than what it is called. Keyed by
# the phrases and CWEs that actually appear in engine output.
DISCLOSURE = "disclosure"        # leaks information an attacker did not have
CREDENTIAL = "credential"        # yields a secret, token, or password
AUTH_BYPASS = "auth_bypass"      # gets past authentication
ACCESS_CONTROL = "access_control"  # reaches another tenant's or role's data
INJECTION = "injection"          # executes attacker input somewhere
SSRF = "ssrf"                    # makes the server issue requests
CLIENT_EXEC = "client_exec"      # runs script in a victim's browser
SESSION = "session"              # weak session handling
UPLOAD = "upload"                # places attacker-controlled files
PRIV_ESC = "priv_esc"            # gains a higher role

_CAPABILITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (DISCLOSURE, re.compile(
        r"information disclosure|sensitive data exposure|verbose error|stack trace|"
        r"directory listing|debug (mode|endpoint)|exposed (config|env|\.git)|"
        r"internal (host|ip|path)|cwe-200|cwe-209|cwe-538", re.I)),
    (CREDENTIAL, re.compile(
        r"hardcoded (secret|credential|password|key)|api key|leaked (token|secret)|"
        r"credentials? in|secret in (source|repo)|cwe-798|cwe-522|cwe-256", re.I)),
    (AUTH_BYPASS, re.compile(
        r"authentication bypass|missing authentication|unauthenticated (access|admin|"
        r"endpoint)|broken authentication|weak (jwt|token) (validation|verification)|"
        r"cwe-287|cwe-306|cwe-305", re.I)),
    (ACCESS_CONTROL, re.compile(
        r"idor|insecure direct object|broken access control|bola|bfla|"
        r"horizontal privilege|missing authorization|cwe-639|cwe-285|cwe-862|cwe-863", re.I)),
    (INJECTION, re.compile(
        r"sql injection|command injection|code injection|template injection|"
        r"deserializ|xxe|ldap injection|nosql injection|cwe-89|cwe-77|cwe-78|"
        r"cwe-94|cwe-502|cwe-611", re.I)),
    (SSRF, re.compile(r"ssrf|server-?side request forgery|cwe-918", re.I)),
    (CLIENT_EXEC, re.compile(
        r"cross-?site scripting|\bxss\b|dom clobbering|cwe-79", re.I)),
    (SESSION, re.compile(
        r"session fixation|missing (httponly|secure) flag|csrf|cross-?site request "
        r"forgery|weak session|predictable session|cwe-352|cwe-384|cwe-614", re.I)),
    (UPLOAD, re.compile(
        r"unrestricted (file )?upload|arbitrary file (write|upload)|path traversal|"
        r"cwe-434|cwe-22", re.I)),
    (PRIV_ESC, re.compile(
        r"privilege escalation|vertical privilege|role escalation|admin takeover|"
        r"cwe-269|cwe-267", re.I)),
]


def capabilities_of(finding: Any) -> set[str]:
    """Which capabilities a finding grants, from its title and classification."""
    haystack = " ".join(
        str(part)
        for part in (
            getattr(finding, "title", "") or "",
            getattr(finding, "owasp_category", "") or "",
        )
    )
    return {name for name, pattern in _CAPABILITY_PATTERNS if pattern.search(haystack)}


# --- Assets ---------------------------------------------------------------
# Two findings chain only if they touch the same thing. The asset key is
# deliberately coarse — a directory, or a host — because an attacker who owns
# one route in a service usually owns its neighbours.
_PATH_SPLIT = re.compile(r"[?#]")


def asset_of(finding: Any) -> str:
    """A coarse key for "the same part of the system"."""
    location = (
        getattr(finding, "file_path", None)
        or (getattr(finding, "evidence", None) or {}).get("target_url")
        or ""
    )
    location = _PATH_SPLIT.split(str(location))[0].strip()
    if not location:
        return ""
    if location.startswith("http://") or location.startswith("https://"):
        # Host plus the first path segment: /api/v1/users and /api/v1/orders
        # are the same service for this purpose.
        without_scheme = location.split("://", 1)[1]
        parts = without_scheme.split("/")
        return "/".join(parts[:2]) if len(parts) > 1 else parts[0]
    # A file path collapses to its directory.
    directory = location.rsplit("/", 1)[0] if "/" in location else location
    return directory.split(":", 1)[0]


# --- Rules ----------------------------------------------------------------
@dataclass(frozen=True)
class ChainRule:
    """A named escalation: these capabilities together mean something worse."""

    title: str
    requires: frozenset[str]
    narrative: str


CHAIN_RULES: tuple[ChainRule, ...] = (
    ChainRule(
        "Credential exposure to account takeover",
        frozenset({CREDENTIAL, AUTH_BYPASS}),
        "A leaked credential and a way past authentication on the same service "
        "compose into full account takeover: the secret supplies the identity "
        "and the bypass removes the check that would have stopped it.",
    ),
    ChainRule(
        "Disclosure to authorization bypass",
        frozenset({DISCLOSURE, ACCESS_CONTROL}),
        "The disclosure supplies the identifiers the broken access control "
        "needs. Alone, each is limited; together an attacker can enumerate "
        "objects and then read them across tenant boundaries.",
    ),
    ChainRule(
        "Session weakness to persistent account compromise",
        frozenset({CLIENT_EXEC, SESSION}),
        "Script execution in a victim's browser plus weak session handling "
        "turns a reflected bug into durable account compromise — the payload "
        "steals or fixates a session the application will keep honouring.",
    ),
    ChainRule(
        "SSRF to internal service access",
        frozenset({SSRF, DISCLOSURE}),
        "Server-side request forgery reaches the internal network, and the "
        "disclosure tells the attacker where to point it. The pair converts a "
        "blind request primitive into targeted access to internal services.",
    ),
    ChainRule(
        "File upload to remote code execution",
        frozenset({UPLOAD, INJECTION}),
        "Attacker-controlled files land somewhere the application will "
        "interpret them. Upload places the payload; the injection flaw gives "
        "it a path to execution.",
    ),
    ChainRule(
        "Access control gap to privilege escalation",
        frozenset({ACCESS_CONTROL, PRIV_ESC}),
        "A missing authorization check next to a role-escalation path lets an "
        "ordinary account promote itself, then use the new role against data "
        "the first flaw already exposed.",
    ),
    ChainRule(
        "Credential exposure to lateral movement",
        frozenset({CREDENTIAL, SSRF}),
        "A recovered credential plus the ability to make the server issue "
        "requests lets an attacker authenticate to internal services from "
        "inside the trust boundary.",
    ),
)


@dataclass
class AttackChain:
    """Several findings that compose into one, worse outcome."""

    title: str
    severity: Severity
    narrative: str
    fingerprints: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "severity": self.severity.value,
            "narrative": self.narrative,
            "fingerprints": list(self.fingerprints),
            "steps": list(self.steps),
        }


def build_chains(findings: Iterable[Any]) -> list[AttackChain]:
    """Find every escalation among ``findings``, worst chain first.

    Only findings that still need attention should be passed in — chaining a
    finding someone already dismissed as a false positive would resurrect it
    through the back door.
    """
    tagged: list[tuple[Any, set[str], str]] = []
    for finding in findings:
        caps = capabilities_of(finding)
        if caps:
            tagged.append((finding, caps, asset_of(finding)))

    # Group by asset. The empty key means "location unknown", which cannot be
    # matched to anything else with confidence, so it is skipped.
    by_asset: dict[str, list[tuple[Any, set[str]]]] = {}
    for finding, caps, asset in tagged:
        if asset:
            by_asset.setdefault(asset, []).append((finding, caps))

    chains: list[AttackChain] = []
    for asset, members in by_asset.items():
        if len(members) < 2:
            continue
        available = set().union(*(caps for _, caps in members))
        for rule in CHAIN_RULES:
            if not rule.requires.issubset(available):
                continue
            links = [f for f, caps in members if caps & rule.requires]
            if len(links) < 2:
                continue
            chains.append(
                AttackChain(
                    title=f"{rule.title} ({asset})",
                    severity=_escalate(
                        _worst(_severity_of(f) for f in links)
                    ),
                    narrative=rule.narrative,
                    fingerprints=[
                        fp for fp in (getattr(f, "fingerprint", None) for f in links) if fp
                    ],
                    steps=[str(getattr(f, "title", "")) for f in links],
                )
            )

    chains.sort(key=lambda c: _SEVERITY_ORDER.index(c.severity))
    return chains


def _severity_of(finding: Any) -> Severity:
    value = getattr(finding, "severity", Severity.INFO)
    if isinstance(value, Severity):
        return value
    try:
        return Severity(str(value))
    except ValueError:
        return Severity.INFO


def serialize(chains: Iterable[AttackChain]) -> list[dict]:
    return [chain.as_dict() for chain in chains]


def deserialize(raw: Optional[list]) -> list[dict]:
    """Read stored chains back, tolerating rows written by an older shape."""
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        out.append(
            {
                "title": item.get("title", ""),
                "severity": item.get("severity", Severity.INFO.value),
                "narrative": item.get("narrative", ""),
                "fingerprints": list(item.get("fingerprints") or []),
                "steps": list(item.get("steps") or []),
            }
        )
    return out
