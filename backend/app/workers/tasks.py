"""Celery tasks — the Strix scan lifecycle lives here.

Flow (see specs §4):
  1. Mark the Scan ``running`` and stamp ``started_at``.
  2. Check out the target repo into a per-scan working directory.
  3. Run Strix headless against the checkout (it spawns its own sandbox).
  4. Parse ``strix_runs/<run>/vulnerabilities.json`` into findings.
  5. Persist findings, mark the Scan ``completed``, and clean up.
On any failure the Scan is marked ``failed`` with the error message.
"""
from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.enums import ScanStatus, ScanTrigger, Severity
from app.models.scan import Scan
from app.models.vulnerability import Vulnerability
from app.services import (
    github_app,
    greybox_instructions,
    repo_checkout,
    strix_report,
    strix_runner,
)
from app.workers.celery_app import celery

logger = get_task_logger(__name__)

# Persisted error messages are truncated to keep them sane in the DB/UI.
_MAX_ERROR_CHARS = 2000


@celery.task(name="app.workers.tasks.run_strix_scan", bind=True)
def run_strix_scan(self, scan_id: str) -> dict:
    """Run a Strix pentest for the given scan and ingest its findings."""
    db = SessionLocal()
    workdir = Path(settings.STRIX_WORK_DIR) / scan_id
    try:
        scan = db.get(Scan, uuid.UUID(scan_id))
        if scan is None:
            logger.warning("Scan %s no longer exists; nothing to do", scan_id)
            return {"scan_id": scan_id, "status": "missing"}

        repo = scan.repository
        is_pr = _is_pr_scan(scan)

        _mark_running(db, scan)
        logger.info("Scan %s running: repo=%s mode=%s", scan_id, repo.name, scan.scan_mode.value)

        # PR scans clone with a GitHub App installation token at the PR commit;
        # everything else clones the default branch with the user's OAuth token.
        if is_pr:
            clone_token = github_app.get_installation_token(scan.github_installation_id)
            clone_ref = scan.github_commit_sha
            _start_pr_check(db, scan, clone_token)
        else:
            clone_token = repo.user.github_token  # decrypted on read
            clone_ref = None

        repo_dir = workdir / "repo"
        repo_checkout.clone_repository(
            repo.url, repo_dir, github_token=clone_token, ref=clone_ref
        )

        # Grey-box: authenticated dynamic testing against a live target, with
        # credentials passed via a mode-0600 instruction file (never on argv).
        greybox = repo.greybox
        if greybox is not None:
            instruction_file = _write_greybox_instructions(workdir, greybox, scan)
            run_dir = strix_runner.run_strix(
                target_dir=repo_dir,
                scan_mode=scan.scan_mode.value,
                workdir=workdir,
                instruction_file=instruction_file,
                extra_targets=[greybox.target_url],
            )
        else:
            run_dir = strix_runner.run_strix(
                target_dir=repo_dir,
                scan_mode=scan.scan_mode.value,
                workdir=workdir,
                instruction=scan.custom_instructions,
            )

        findings = strix_report.parse_report(run_dir)
        _persist_findings(db, scan, findings)
        _mark_completed(db, scan)

        if is_pr:
            _report_pr_result(scan, findings)

        logger.info("Scan %s completed with %d finding(s)", scan_id, len(findings))
        return {"scan_id": scan_id, "status": ScanStatus.COMPLETED.value, "findings": len(findings)}

    except SoftTimeLimitExceeded:
        _fail(db, scan_id, "Scan exceeded the maximum allowed run time.")
        _report_pr_failure(db, scan_id)
        raise
    except (
        repo_checkout.CheckoutError,
        strix_runner.StrixError,
        ValueError,
    ) as exc:
        # Expected, user-actionable failures (bad repo, engine/report error).
        logger.warning("Scan %s failed: %s", scan_id, exc)
        _fail(db, scan_id, str(exc))
        _report_pr_failure(db, scan_id)
        return {"scan_id": scan_id, "status": ScanStatus.FAILED.value}
    except Exception as exc:  # noqa: BLE001 - last-resort guard so the row never stays 'running'
        logger.exception("Scan %s failed unexpectedly", scan_id)
        _fail(db, scan_id, f"Unexpected error: {exc}")
        _report_pr_failure(db, scan_id)
        return {"scan_id": scan_id, "status": ScanStatus.FAILED.value}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        db.close()


# --- GitHub pull-request feedback ----------------------------------------
def _is_pr_scan(scan: Scan) -> bool:
    return scan.trigger == ScanTrigger.PULL_REQUEST and bool(scan.github_installation_id)


def _severity_counts(findings: list[strix_report.ParsedFinding]) -> dict[str, int]:
    counts = {s.value: 0 for s in Severity}
    for f in findings:
        counts[f.severity.value] += 1
    return counts


def _report_url(scan: Scan) -> str:
    return f"{settings.DASHBOARD_URL}/scans/{scan.id}"


def _start_pr_check(db, scan: Scan, token: str) -> None:
    """Open an in-progress check run so the PR shows Aegis is running."""
    try:
        check_run_id = github_app.create_check_run(
            token, scan.repository.name, scan.github_commit_sha
        )
        if check_run_id:
            scan.github_check_run_id = check_run_id
            db.commit()
    except Exception:  # noqa: BLE001 - feedback must never break the scan
        logger.exception("Failed to open check run for scan %s", scan.id)


def _report_pr_result(scan: Scan, findings: list[strix_report.ParsedFinding]) -> None:
    try:
        counts = _severity_counts(findings)
        total = len(findings)
        token = github_app.get_installation_token(scan.github_installation_id)
        repo_full = scan.repository.name

        body = github_app.format_findings_comment(
            counts, findings, total=total, report_url=_report_url(scan)
        )
        github_app.upsert_pr_comment(token, repo_full, scan.github_pr_number, body)

        if scan.github_check_run_id:
            title, summary = github_app.check_summary(total, counts)
            github_app.update_check_run(
                token,
                repo_full,
                scan.github_check_run_id,
                conclusion=github_app.check_conclusion(counts),
                title=title,
                summary=summary,
            )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to report PR result for scan %s", scan.id)


def _report_pr_failure(db, scan_id: str) -> None:
    scan = db.get(Scan, uuid.UUID(scan_id))
    if scan is None or not _is_pr_scan(scan) or not scan.github_check_run_id:
        return
    try:
        token = github_app.get_installation_token(scan.github_installation_id)
        github_app.update_check_run(
            token,
            scan.repository.name,
            scan.github_check_run_id,
            conclusion="neutral",
            title="Scan did not complete",
            summary=scan.error_message or "The Aegis scan failed to complete.",
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to report PR failure for scan %s", scan_id)


def _write_greybox_instructions(workdir: Path, greybox, scan: Scan) -> Path:
    """Write the auth instruction file (0600) in the ephemeral workdir.

    ``greybox.password`` / ``greybox.extra`` are decrypted transparently on
    read; the file lives only for the scan and is removed with the workdir.
    """
    text = greybox_instructions.build_instruction(
        target_url=greybox.target_url,
        login_url=greybox.login_url,
        username=greybox.username,
        password=greybox.password,
        extra=greybox.extra,
        custom_instructions=scan.custom_instructions,
    )
    path = workdir / "instructions.txt"
    path.write_text(text, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - best-effort on non-POSIX hosts
        pass
    return path


def _mark_running(db, scan: Scan) -> None:
    scan.status = ScanStatus.RUNNING
    scan.started_at = _now()
    scan.error_message = None
    db.commit()


def _mark_completed(db, scan: Scan) -> None:
    scan.status = ScanStatus.COMPLETED
    scan.completed_at = _now()
    db.commit()


def _persist_findings(db, scan: Scan, findings: list[strix_report.ParsedFinding]) -> None:
    for f in findings:
        db.add(
            Vulnerability(
                scan_id=scan.id,
                severity=f.severity,
                title=f.title[:512],
                description=f.description,
                poc_code=f.poc_code,
                remediation=f.remediation,
                owasp_category=f.owasp_category[:128] if f.owasp_category else None,
                cvss_score=f.cvss_score,
                file_path=f.file_path,
            )
        )
    db.flush()


def _fail(db, scan_id: str, message: str) -> None:
    """Mark a scan ``failed`` on a clean session, tolerating a poisoned one."""
    db.rollback()
    scan = db.get(Scan, uuid.UUID(scan_id))
    if scan is None:
        return
    scan.status = ScanStatus.FAILED
    scan.completed_at = _now()
    scan.error_message = message[:_MAX_ERROR_CHARS]
    db.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)


@celery.task(name="app.workers.tasks.enqueue_due_scheduled_scans", bind=True)
def enqueue_due_scheduled_scans(self) -> dict:
    """Beat tick: dispatch a scan for every schedule that is due.

    For each due schedule we advance ``next_run_at`` first (so a transient
    error can't cause a tight re-dispatch loop), then enqueue a scan — but only
    if the owner is still entitled (verified email + active subscription within
    quota). Un-entitled schedules are skipped and retried next period.
    """
    # Imported lazily to avoid a circular import (scan_service imports this module).
    from app.services import billing, scan_service, schedule_service

    db = SessionLocal()
    dispatched = 0
    skipped = 0
    try:
        due = schedule_service.due_schedules(db)
        for schedule in due:
            schedule_service.advance_after_dispatch(db, schedule)

            repo = schedule.repository
            user = repo.user
            if not user.email_verified:
                skipped += 1
                continue
            try:
                billing.assert_can_create_scan(db, user)
            except billing.PaymentRequiredError:
                skipped += 1
                continue

            scan_service.create_scan(
                db,
                user=user,
                repository_id=repo.id,
                scan_mode=schedule.scan_mode,
                custom_instructions=schedule.custom_instructions,
                trigger=ScanTrigger.SCHEDULED,
            )
            dispatched += 1

        if due:
            logger.info(
                "Scheduled scans: %d dispatched, %d skipped", dispatched, skipped
            )
        return {"dispatched": dispatched, "skipped": skipped}
    except Exception:  # noqa: BLE001 - a beat tick must never crash the worker
        logger.exception("enqueue_due_scheduled_scans failed")
        db.rollback()
        return {"dispatched": dispatched, "skipped": skipped, "error": True}
    finally:
        db.close()
