"""Tests for persisted scan-error truncation (workers/tasks.py)."""
from __future__ import annotations

from app.workers.tasks import _ELISION, _MAX_ERROR_CHARS, _truncate_error


def test_short_message_is_untouched() -> None:
    assert _truncate_error("boom") == "boom"


def test_exact_limit_is_untouched() -> None:
    message = "x" * _MAX_ERROR_CHARS
    assert _truncate_error(message) == message


def test_long_message_keeps_both_ends() -> None:
    message = "HEAD-NAMES-THE-FAILURE" + ("x" * 5000) + "TAIL-NAMES-THE-CAUSE"
    result = _truncate_error(message)

    assert len(result) <= _MAX_ERROR_CHARS
    assert result.startswith("HEAD-NAMES-THE-FAILURE")
    assert result.endswith("TAIL-NAMES-THE-CAUSE")
    assert _ELISION in result
