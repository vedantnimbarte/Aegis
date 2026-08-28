"""Stable identity for a finding across re-scans.

Strix assigns a fresh id to every finding on every run, so "is this the same
issue we saw last week?" has to be answered from the finding's content. We
hash the parts that stay put when unrelated code moves around:

    title + file path + classification (CWE/CVE)

Deliberately *not* included: line numbers, PoC text, descriptions, and CVSS.
Those wobble between runs of a non-deterministic agent, and including them
would make every scan look like an entirely new set of problems.

The trade-off runs the other way too: two genuinely distinct issues that share
a title, file, and CWE collapse into one fingerprint. That is the safer
direction — it under-reports "new" rather than crying wolf every scan.

Pure and dependency-free so the hashing rules can be unit-tested directly.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

# Collapse whitespace runs so trivial reformatting doesn't change identity.
_WHITESPACE = re.compile(r"\s+")


def _normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    return _WHITESPACE.sub(" ", value).strip().lower()


def fingerprint(
    *,
    title: Optional[str],
    file_path: Optional[str] = None,
    classification: Optional[str] = None,
) -> str:
    """Return a 64-char hex digest identifying this finding.

    Always returns a value: a finding with no title at all still needs *some*
    identity, and an empty-input hash is a stable, harmless bucket.
    """
    material = "\x1f".join(
        (_normalize(title), _normalize(file_path), _normalize(classification))
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
