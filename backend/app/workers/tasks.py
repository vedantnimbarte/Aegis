"""Celery tasks — the Strix scan lifecycle lives here.

This is a placeholder signature for phase 1. The full implementation (Docker
orchestration, repo checkout, report ingestion) lands in a later phase.
"""
from __future__ import annotations

from app.workers.celery_app import celery


@celery.task(name="app.workers.tasks.run_strix_scan", bind=True)
def run_strix_scan(self, scan_id: str) -> dict:
    """Run a Strix pentest for the given scan.

    Lifecycle (see specs §4):
      1. Mark the Scan `running`, stamp `started_at`.
      2. Check out the target repo into a temp dir.
      3. `docker run --rm -v <repo>:/app -e STRIX_LLM=... usestrix/strix -n --target /app`
      4. Parse `strix_runs/<run>/report.json`.
      5. Map findings -> Vulnerabilities, mark Scan `completed`, clean up.
      On any failure: mark Scan `failed` with the error message.

    TODO(phase-3): implement the Docker orchestration + report ingestion.
    """
    return {"detail": "Not implemented", "scan_id": scan_id}
