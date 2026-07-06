"""Parse Strix's ``vulnerabilities.json`` into Aegis findings.

This module is intentionally free of framework/settings imports so the
mapping can be unit-tested in isolation. It knows only about the on-disk
Strix report format and the Aegis ``Severity`` enum.

Strix writes results to ``strix_runs/<run_name>/`` (see specs §4). The
machine-readable findings live in ``vulnerabilities.json`` — a JSON array of
objects whose shape is reverse-engineered from Strix's report writer
(``strix/report/state.py``). Relevant fields per finding:

    id, title, severity, description, impact, target, technical_analysis,
    poc_description, poc_script_code, remediation_steps, cvss, cvss_breakdown,
    endpoint, method, cve, cwe, code_locations[]

Strix has no OWASP-category field; we surface the CWE (falling back to CVE)
in ``owasp_category`` as the closest available classification for the UI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.models.enums import Severity

# The findings file Strix writes inside each run directory.
VULNERABILITIES_FILENAME = "vulnerabilities.json"

_SEVERITY_BY_VALUE = {s.value: s for s in Severity}


@dataclass(frozen=True)
class ParsedFinding:
    """A normalized finding, aligned 1:1 with the ``Vulnerability`` model."""

    severity: Severity
    title: str
    description: str
    poc_code: Optional[str] = None
    remediation: Optional[str] = None
    owasp_category: Optional[str] = None
    cvss_score: Optional[float] = None
    file_path: Optional[str] = None


def parse_report(run_dir: Path) -> list[ParsedFinding]:
    """Read and normalize every finding in a Strix run directory.

    A completed scan with no findings is normal — if the file is missing or
    holds an empty array we return ``[]``. A file that exists but cannot be
    parsed is an ingestion error and raises ``ValueError`` so the caller can
    fail the scan explicitly rather than silently dropping results.
    """
    report_path = run_dir / VULNERABILITIES_FILENAME
    if not report_path.is_file():
        return []

    try:
        raw = json.loads(report_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Could not read Strix report {report_path}: {exc}") from exc

    # Strix writes a top-level array; tolerate a wrapped {"vulnerabilities": [...]}.
    if isinstance(raw, dict):
        raw = raw.get("vulnerabilities") or raw.get("findings") or []
    if not isinstance(raw, list):
        raise ValueError(
            f"Unexpected Strix report shape in {report_path}: {type(raw).__name__}"
        )

    return [_map_finding(item) for item in raw if isinstance(item, dict)]


def _map_finding(item: dict[str, Any]) -> ParsedFinding:
    """Map one raw Strix finding dict onto a ``ParsedFinding``."""
    return ParsedFinding(
        severity=_coerce_severity(item.get("severity")),
        title=_coerce_str(item.get("title")) or "Untitled finding",
        description=_build_description(item),
        poc_code=_coerce_str(item.get("poc_script_code")) or None,
        remediation=_build_remediation(item),
        owasp_category=_coerce_str(item.get("cwe"))
        or _coerce_str(item.get("cve"))
        or None,
        cvss_score=_coerce_float(item.get("cvss")),
        file_path=_primary_file_path(item),
    )


def _coerce_severity(value: Any) -> Severity:
    """Map a Strix severity string onto our enum, defaulting to INFO."""
    if isinstance(value, str):
        return _SEVERITY_BY_VALUE.get(value.strip().lower(), Severity.INFO)
    return Severity.INFO


def _coerce_str(value: Any) -> str:
    """Coerce scalars/lists into a trimmed string; lists become bullet lines."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        parts = [_coerce_str(v) for v in value]
        return "\n".join(f"- {p}" for p in parts if p)
    return str(value).strip()


def _coerce_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):  # bool is an int subclass — reject explicitly
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _build_description(item: dict[str, Any]) -> str:
    """Compose a rich markdown description from Strix's narrative fields.

    The ``Vulnerability`` model has a single ``description`` column, so we
    fold Strix's impact / technical analysis / PoC narrative and the affected
    target into one well-structured body rather than discarding them.
    """
    sections: list[str] = []

    def add(heading: str, value: Any) -> None:
        text = _coerce_str(value)
        if text:
            sections.append(f"### {heading}\n{text}")

    add("Description", item.get("description"))
    add("Impact", item.get("impact"))
    add("Technical analysis", item.get("technical_analysis"))
    add("Proof of concept", item.get("poc_description"))

    # Affected target / endpoint context.
    target_bits: list[str] = []
    method = _coerce_str(item.get("method"))
    endpoint = _coerce_str(item.get("endpoint"))
    target = _coerce_str(item.get("target"))
    if method or endpoint:
        target_bits.append(" ".join(b for b in (method, endpoint) if b))
    elif target:
        target_bits.append(target)
    if target_bits:
        sections.append(f"### Affected target\n{target_bits[0]}")

    body = "\n\n".join(sections)
    return body or "No description provided by Strix."


def _build_remediation(item: dict[str, Any]) -> Optional[str]:
    """Remediation guidance, plus any suggested code fix from code_locations."""
    parts: list[str] = []

    steps = _coerce_str(item.get("remediation_steps"))
    if steps:
        parts.append(steps)

    for loc in item.get("code_locations") or []:
        if not isinstance(loc, dict):
            continue
        before = _coerce_str(loc.get("fix_before"))
        after = _coerce_str(loc.get("fix_after"))
        if not (before or after):
            continue
        where = _format_location(loc)
        block = [f"Suggested fix{f' in {where}' if where else ''}:"]
        if before:
            block.append(f"```diff\n- {before}\n```")
        if after:
            block.append(f"```diff\n+ {after}\n```")
        parts.append("\n".join(block))

    return "\n\n".join(parts) or None


def _primary_file_path(item: dict[str, Any]) -> Optional[str]:
    """Best-effort affected file, from the first whitebox code location."""
    for loc in item.get("code_locations") or []:
        if isinstance(loc, dict):
            where = _format_location(loc)
            if where:
                return where[:1024]
    endpoint = _coerce_str(item.get("endpoint"))
    return endpoint[:1024] or None if endpoint else None


def _format_location(loc: dict[str, Any]) -> str:
    """Render a code location as ``file:start-end`` (parts optional)."""
    file = _coerce_str(loc.get("file"))
    if not file:
        return ""
    start = loc.get("start_line")
    end = loc.get("end_line")
    if isinstance(start, int) and isinstance(end, int) and end != start:
        return f"{file}:{start}-{end}"
    if isinstance(start, int):
        return f"{file}:{start}"
    return file
