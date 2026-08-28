"""Finding aggregation for the scans list and the overview page."""
from __future__ import annotations

import uuid

from app.models.enums import Severity
from app.services.scan_service import summarize_findings

REPO = uuid.uuid4()
SCAN_A = uuid.uuid4()
SCAN_B = uuid.uuid4()


def test_counts_group_per_scan_and_severity() -> None:
    rows = [
        (SCAN_A, REPO, Severity.CRITICAL, "fp1"),
        (SCAN_A, REPO, Severity.CRITICAL, "fp2"),
        (SCAN_A, REPO, Severity.LOW, "fp3"),
        (SCAN_B, REPO, Severity.HIGH, "fp4"),
    ]

    out = summarize_findings(rows, frozenset())

    assert out[SCAN_A].counts_by_severity["critical"] == 2
    assert out[SCAN_A].counts_by_severity["low"] == 1
    assert out[SCAN_A].counts_by_severity["high"] == 0
    assert out[SCAN_A].total == 3
    assert out[SCAN_B].counts_by_severity["high"] == 1
    assert out[SCAN_B].total == 1


def test_triaged_findings_leave_the_severity_counts_but_stay_in_total() -> None:
    rows = [
        (SCAN_A, REPO, Severity.CRITICAL, "keep"),
        (SCAN_A, REPO, Severity.CRITICAL, "dismissed"),
    ]

    out = summarize_findings(rows, frozenset({(REPO, "dismissed")}))

    assert out[SCAN_A].counts_by_severity["critical"] == 1
    assert out[SCAN_A].suppressed == 1
    assert out[SCAN_A].total == 2


def test_suppression_is_scoped_to_its_own_repository() -> None:
    """A verdict in one repo must not silence the same fingerprint in another."""
    other_repo = uuid.uuid4()
    rows = [(SCAN_B, other_repo, Severity.HIGH, "shared")]

    out = summarize_findings(rows, frozenset({(REPO, "shared")}))

    assert out[SCAN_B].counts_by_severity["high"] == 1
    assert out[SCAN_B].suppressed == 0


def test_findings_without_a_fingerprint_are_never_suppressed() -> None:
    rows = [(SCAN_A, REPO, Severity.MEDIUM, None)]

    out = summarize_findings(rows, frozenset())

    assert out[SCAN_A].counts_by_severity["medium"] == 1
    assert out[SCAN_A].suppressed == 0
