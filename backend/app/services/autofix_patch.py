"""Apply Strix's suggested before/after fixes to file content.

Pure and dependency-free so the patch logic is unit-testable in isolation. Each
fix is applied as a single literal replacement of ``fix_before`` with
``fix_after``; a fix whose ``fix_before`` isn't found is skipped (the file may
have changed since the scan), so we never corrupt unrelated code.
"""
from __future__ import annotations

from typing import Any


def apply_fixes(content: str, fixes: list[dict[str, Any]]) -> tuple[str, int]:
    """Return ``(new_content, applied_count)`` after applying ``fixes``."""
    applied = 0
    for fix in fixes:
        before = fix.get("fix_before")
        after = fix.get("fix_after")
        if not (before and after):
            continue
        if before in content:
            content = content.replace(before, after, 1)
            applied += 1
    return content, applied
