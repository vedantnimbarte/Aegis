"""Recording what a scan spent.

The interesting cases are the unhappy ones: a run that burned tokens and then
failed still cost money, and a run that never reached Strix must not be written
down as having cost nothing.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace

from app.workers import tasks

SCAN_ID = str(uuid.uuid4())


class _StubSession:
    """Hands back one scan and remembers whether the write was committed."""

    def __init__(self, scan) -> None:
        self.scan = scan
        self.committed = False
        self.rolled_back = 0

    def get(self, _model, _pk):
        return self.scan

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back += 1


def _scan():
    return SimpleNamespace(
        id=SCAN_ID, engine_model=None, cost_usd=None,
        llm_requests=None, input_tokens=None, output_tokens=None,
    )


def _workdir_with_usage(tmp_path: Path, **usage) -> Path:
    """A scan workdir holding the run state Strix leaves behind."""
    run = tmp_path / "strix_runs" / "run-1"
    run.mkdir(parents=True)
    (run / "run.json").write_text(
        json.dumps({"run_id": "run-1", "status": "finished", "llm_usage": usage}),
        encoding="utf-8",
    )
    return tmp_path


def test_a_failed_run_still_records_what_it_spent(tmp_path: Path) -> None:
    scan = _scan()
    db = _StubSession(scan)
    workdir = _workdir_with_usage(
        tmp_path, cost=1.25, requests=9, input_tokens=1000, output_tokens=200
    )

    tasks._record_usage(db, SCAN_ID, workdir, "openai/gpt-4o")

    assert scan.cost_usd == 1.25
    assert scan.llm_requests == 9
    assert scan.engine_model == "openai/gpt-4o"
    assert db.committed


def test_a_run_that_never_started_leaves_the_columns_empty(tmp_path: Path) -> None:
    """No run state means no data — not a zero, which would read as 'free'."""
    scan = _scan()
    db = _StubSession(scan)

    tasks._record_usage(db, SCAN_ID, tmp_path, None)

    assert scan.cost_usd is None
    assert scan.llm_requests is None


def test_a_missing_scan_is_not_an_error(tmp_path: Path) -> None:
    db = _StubSession(None)
    tasks._record_usage(db, SCAN_ID, tmp_path, "openai/gpt-4o")
    assert not db.committed


def test_accounting_never_raises_at_the_caller(tmp_path: Path) -> None:
    """It runs in a finally on the failure paths; it must not mask the error."""

    class _Exploding(_StubSession):
        def get(self, _model, _pk):
            raise RuntimeError("session is poisoned")

    db = _Exploding(_scan())
    tasks._record_usage(db, SCAN_ID, tmp_path, None)  # must not raise
    assert db.rolled_back >= 1
