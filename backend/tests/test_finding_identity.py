"""Tests for finding fingerprints (services/finding_identity.py)."""
from __future__ import annotations

from app.services.finding_identity import fingerprint


def test_same_finding_yields_same_fingerprint() -> None:
    a = fingerprint(title="SQL Injection", file_path="app/db.py", classification="CWE-89")
    b = fingerprint(title="SQL Injection", file_path="app/db.py", classification="CWE-89")
    assert a == b


def test_fingerprint_is_case_and_whitespace_insensitive() -> None:
    a = fingerprint(title="SQL Injection", file_path="app/db.py")
    b = fingerprint(title="  sql   injection ", file_path="APP/DB.PY")
    assert a == b


def test_different_file_is_a_different_finding() -> None:
    a = fingerprint(title="SQL Injection", file_path="app/db.py")
    b = fingerprint(title="SQL Injection", file_path="app/api.py")
    assert a != b


def test_different_classification_is_a_different_finding() -> None:
    a = fingerprint(title="Injection", file_path="a.py", classification="CWE-89")
    b = fingerprint(title="Injection", file_path="a.py", classification="CWE-78")
    assert a != b


def test_empty_finding_still_gets_a_stable_id() -> None:
    assert fingerprint(title=None) == fingerprint(title="")
    assert len(fingerprint(title=None)) == 64
