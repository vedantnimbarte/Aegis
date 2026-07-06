"""Tests for auto-fix patch application and Strix fix extraction."""
from __future__ import annotations

from app.services import autofix_patch
from app.services import strix_report


def test_applies_matching_fix() -> None:
    content = "def q(u):\n    return f'... {u}'\n"
    fixes = [{"fix_before": "return f'... {u}'", "fix_after": "return '... %s', (u,)"}]
    out, n = autofix_patch.apply_fixes(content, fixes)
    assert n == 1
    assert "return '... %s', (u,)" in out
    assert "f'... {u}'" not in out


def test_skips_fix_not_found() -> None:
    content = "unchanged code\n"
    fixes = [{"fix_before": "nonexistent", "fix_after": "whatever"}]
    out, n = autofix_patch.apply_fixes(content, fixes)
    assert n == 0
    assert out == content


def test_applies_only_first_occurrence() -> None:
    content = "x = 1\nx = 1\n"
    out, n = autofix_patch.apply_fixes(content, [{"fix_before": "x = 1", "fix_after": "x = 2"}])
    assert n == 1
    assert out == "x = 2\nx = 1\n"


def test_ignores_incomplete_fixes() -> None:
    content = "code"
    out, n = autofix_patch.apply_fixes(
        content, [{"fix_before": "code"}, {"fix_after": "x"}, {}]
    )
    assert n == 0
    assert out == content


# --- Strix fix extraction -------------------------------------------------
def test_extract_fixes_from_code_locations() -> None:
    item = {
        "code_locations": [
            {"file": "app/auth.py", "fix_before": "a", "fix_after": "b"},
            {"file": "app/x.py", "fix_before": "same", "fix_after": "same"},  # no-op
            {"file": "app/y.py", "fix_before": "only-before"},  # incomplete
        ]
    }
    fixes = strix_report._extract_fixes(item)
    assert fixes == [{"file": "app/auth.py", "fix_before": "a", "fix_after": "b"}]


def test_extract_fixes_none_when_absent() -> None:
    assert strix_report._extract_fixes({}) is None
    assert strix_report._extract_fixes({"code_locations": []}) is None
