"""Celery tasks — the Strix scan lifecycle lives here.

Flow (see specs §4):
  1. Mark the Scan ``running`` and stamp ``started_at``.
  2. Prepare the target: clone a repository, or address a live endpoint.
  3. Run Strix headless against it (it spawns its own sandbox).
  4. Parse ``strix_runs/<run>/vulnerabilities.json`` into findings.
  5. Persist findings with their evidence, compute attack chains, mark the
     Scan ``completed``, and clean up.
On any failure the Scan is marked ``failed`` with the error message.

A retest is the same machinery pointed at one question — "does this exploit
still work?" — and its result is written to the finding's triage row rather
than reported as a fresh survey.
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
from app.models.enums import (
    RetestOutcome,
    ScanStatus,
    ScanTrigger,
    Severity,
    TargetKind,
)
from app.models.scan import Scan
from app.models.target import Target
from app.models.vulnerability import Vulnerability
from app.services import (
    ai_testing,
    api_spec,
    attack_paths,
    audit_service,
    billing_plans,
    evidence as evidence_service,
    finding_identity,
    gate,
    github_app,
    greybox_instructions,
    notifications,
    repo_checkout,
    retest as retest_service,
    scan_progress,
    source_hosts,
    strix_report,
    strix_runner,
    triage_service,
)
from app.workers.celery_app import celery

logger = get_task_logger(__name__)

# Persisted error messages are truncated to keep them sane in the DB/UI.
_MAX_ERROR_CHARS = 2000
_ELISION = "\n…[truncated]…\n"


def _truncate_error(message: str) -> str:
    """Trim a long error to ``_MAX_ERROR_CHARS``, keeping BOTH ends.

    Head-only truncation loses the cause: a Strix/Docker traceback names the
    failure in its last lines, so cutting the tail leaves an unactionable
    stack. Keep a slice of each and mark the gap.
    """
    if len(message) <= _MAX_ERROR_CHARS:
        return message
    budget = _MAX_ERROR_CHARS - len(_ELISION)
    head = budget // 3
    return message[:head] + _ELISION + message[-(budget - head):]


@celery.task(name="app.workers.tasks.run_strix_scan", bind=True)
def run_strix_scan(self, scan_id: str) -> dict:
    """Run a Strix pentest for the given scan and ingest its findings."""
    db = SessionLocal()
    workdir = Path(settings.STRIX_WORK_DIR) / scan_id
    # Bound before the try so the finally can record usage no matter how early
    # the run fell over.
    model: Optional[str] = None
    try:
        scan = db.get(Scan, uuid.UUID(scan_id))
        if scan is None:
            logger.warning("Scan %s no longer exists; nothing to do", scan_id)
            return {"scan_id": scan_id, "status": "missing"}

        target = scan.target
        is_pr = _is_pr_scan(scan)

        _mark_running(db, scan)
        logger.info(
            "Scan %s running: target=%s kind=%s mode=%s",
            scan_id, target.name, target.kind.value, scan.scan_mode.value,
        )

        repo_dir = _prepare_source(db, scan, target, workdir) if target.needs_checkout else None
        model, api_key = _llm_credentials(db, target)

        plan = _build_plan(db, scan, target, workdir, repo_dir)
        run_dir = strix_runner.run_strix(
            target_dir=repo_dir,
            extra_targets=plan.extra_targets,
            scan_mode=scan.scan_mode.value,
            workdir=workdir,
            instruction=plan.instruction,
            instruction_file=plan.instruction_file,
            llm_model=model,
            llm_api_key=api_key,
            max_budget_usd=target.max_budget_usd,
        )

        findings = strix_report.parse_report(run_dir)
        _persist_findings(db, scan, target, findings, plan.commit_sha, model)
        _mark_completed(db, scan)

        if scan.is_retest:
            _record_retest_result(db, scan, target, findings, model, plan.commit_sha)
        else:
            _store_attack_chains(db, scan)

        if is_pr:
            _report_pr_result(db, scan, target, findings)
        _notify(db, scan_id, ScanStatus.COMPLETED.value, findings)

        logger.info("Scan %s completed with %d finding(s)", scan_id, len(findings))
        return {"scan_id": scan_id, "status": ScanStatus.COMPLETED.value, "findings": len(findings)}

    except SoftTimeLimitExceeded:
        _fail(db, scan_id, "Scan exceeded the maximum allowed run time.")
        _mark_retest_inconclusive(db, scan_id)
        _report_pr_failure(db, scan_id)
        _notify(db, scan_id, ScanStatus.FAILED.value)
        raise
    except (
        repo_checkout.CheckoutError,
        strix_runner.StrixError,
        source_hosts.SourceHostError,
        ValueError,
    ) as exc:
        # Expected, user-actionable failures (bad repo, engine/report error).
        logger.warning("Scan %s failed: %s", scan_id, exc)
        _fail(db, scan_id, str(exc))
        _mark_retest_inconclusive(db, scan_id)
        _report_pr_failure(db, scan_id)
        _notify(db, scan_id, ScanStatus.FAILED.value)
        return {"scan_id": scan_id, "status": ScanStatus.FAILED.value}
    except Exception as exc:  # noqa: BLE001 - last-resort guard so the row never stays 'running'
        logger.exception("Scan %s failed unexpectedly", scan_id)
        _fail(db, scan_id, f"Unexpected error: {exc}")
        _mark_retest_inconclusive(db, scan_id)
        _report_pr_failure(db, scan_id)
        _notify(db, scan_id, ScanStatus.FAILED.value)
        return {"scan_id": scan_id, "status": ScanStatus.FAILED.value}
    finally:
        # Must come before the rmtree: the spend is read out of the run state
        # that this line deletes.
        _record_usage(db, scan_id, workdir, model)
        shutil.rmtree(workdir, ignore_errors=True)
        db.close()


# --- Run planning ---------------------------------------------------------
class _RunPlan:
    """How this particular target gets attacked.

    Assembled in one place because the differences between kinds are all
    decided here: which URLs go on the command line, whether credentials need
    an instruction *file* rather than an argument, and what the agents are
    told to look for.
    """

    def __init__(self) -> None:
        self.extra_targets: list[str] = []
        self.instruction: Optional[str] = None
        self.instruction_file: Optional[Path] = None
        self.commit_sha: Optional[str] = None


def _build_plan(
    db, scan: Scan, target: Target, workdir: Path, repo_dir: Optional[Path]
) -> _RunPlan:
    plan = _RunPlan()
    plan.commit_sha = scan.github_commit_sha
    greybox = target.greybox
    live_url = target.live_url

    if live_url:
        plan.extra_targets.append(live_url)

    # A retest overrides everything else: it exists to answer one question,
    # and a broader instruction would turn it back into a survey.
    if scan.is_retest and scan.retest_fingerprint:
        plan.instruction = _retest_instruction(db, scan, target, live_url)
        return plan

    # AI-layer targets get the OWASP GenAI test plan rather than a web one.
    if ai_testing.supports(target.kind) and live_url:
        plan.instruction = ai_testing.build_instruction(
            target.kind,
            target_url=live_url,
            custom_instructions=scan.custom_instructions,
            auth_notes=_auth_notes(greybox),
        )
        return plan

    # Credentials never go on the command line, so grey-box uses a 0600 file.
    if greybox is not None:
        plan.instruction_file = _write_greybox_instructions(workdir, greybox, scan)
        return plan

    instructions: list[str] = []
    if scan.custom_instructions and scan.custom_instructions.strip():
        instructions.append(scan.custom_instructions.strip())

    # An API target with routes derived from source gets them as context; a
    # scanner with no route list crawls a single-page app and finds nothing.
    spec_note = _api_spec_note(db, target, repo_dir)
    if spec_note:
        instructions.append(spec_note)

    plan.instruction = "\n\n".join(instructions) or None
    return plan


def _auth_notes(greybox) -> Optional[str]:
    """Credentials for an AI-layer target, if the team configured any."""
    if greybox is None:
        return None
    bits = []
    if greybox.username:
        bits.append(f'username "{greybox.username}"')
    if greybox.password:
        bits.append(f'password "{greybox.password}"')
    if greybox.extra:
        bits.append(greybox.extra)
    return "; ".join(bits) or None


def _retest_instruction(
    db, scan: Scan, target: Target, live_url: Optional[str]
) -> str:
    """Rebuild the exploit brief for the single finding under retest."""
    from app.services import scan_service

    finding = scan_service.find_latest_finding(
        db, target.id, scan.retest_fingerprint or ""
    )
    if finding is None:
        # The finding was deleted with its scan. Nothing to re-run.
        raise ValueError("The finding to retest no longer exists.")
    return retest_service.build_instruction(
        title=finding.title,
        fingerprint=scan.retest_fingerprint or "",
        description=finding.description,
        poc_code=finding.poc_code,
        file_path=finding.file_path,
        target_url=live_url,
        remediation=finding.remediation,
    )


def _api_spec_note(db, target: Target, repo_dir: Optional[Path]) -> Optional[str]:
    """Derive routes from the checkout and describe them for the agents.

    Best-effort throughout: a repository we cannot read routes out of is the
    normal case for plenty of stacks, and it must never fail a scan.
    """
    if not settings.API_SPEC_ENABLED or repo_dir is None:
        return None
    try:
        document = api_spec.derive_spec(
            repo_dir,
            title=target.name,
            server_url=target.live_url,
            max_files=settings.API_SPEC_MAX_FILES,
            max_file_bytes=settings.API_SPEC_MAX_FILE_BYTES,
        )
    except Exception:  # noqa: BLE001 - route inference is an optimization
        logger.warning("API spec inference failed for target %s", target.id, exc_info=True)
        return None
    if not document:
        return None

    try:
        target.derived_spec = document
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    routes = sorted(document.get("paths", {}).keys())
    logger.info("Target %s: %s", target.id, api_spec.summarize(document))
    listed = "\n".join(f"- {path}" for path in routes[:200])
    return (
        "# API routes discovered in source\n\n"
        "These endpoints were derived from the application's own code. Exercise "
        "them directly rather than relying on crawling, and test each for broken "
        "object-level authorization (BOLA), broken function-level authorization "
        "(BFLA), IDOR, and missing authentication.\n\n" + listed
    )


def _prepare_source(db, scan: Scan, target: Target, workdir: Path) -> Path:
    """Clone the target repository, using the right credential for its host."""
    is_pr = _is_pr_scan(scan)
    repo_dir = workdir / "repo"

    if is_pr:
        # PR scans clone with a GitHub App installation token at the PR commit.
        token = github_app.get_installation_token(scan.github_installation_id)
        username = "x-access-token"
        ref = scan.github_commit_sha
        _start_pr_check(db, scan, token)
    else:
        owner = target.organization.owner
        provider = target.provider
        token = source_hosts.token_for(owner, provider) if provider else None
        username = source_hosts.clone_username(provider) if provider else "x-access-token"
        ref = None

    repo_checkout.clone_repository(
        target.clone_url,
        repo_dir,
        github_token=token,
        token_username=username,
        ref=ref,
    )
    return repo_dir


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


def _llm_credentials(db, target: Target) -> tuple[Optional[str], Optional[str]]:
    """The model and key this scan runs on.

    BYOK when the organization's billing user set one and their tier allows
    it; otherwise the platform's shared configuration. The model is returned
    either way so it can be recorded as evidence provenance.
    """
    from app.services import org_service

    payer = org_service.billing_user(db, target.organization)
    if payer.llm_api_key and billing_plans.limits_for(payer.subscription_tier).byok:
        return payer.llm_model or settings.STRIX_LLM, payer.llm_api_key
    return settings.STRIX_LLM, None


def _notify(db, scan_id: str, status: str, findings=None) -> None:
    """Notify the scan owner it finished — by email, and Slack if configured.

    Re-fetches on a clean session so it works on the failure paths too. PR scans
    are skipped for email since they already report in the pull request itself.
    Both channels are best-effort and swallow their own delivery errors.
    """
    db.rollback()  # tolerate a poisoned session on the failure paths
    scan = db.get(Scan, uuid.UUID(scan_id))
    if scan is None:
        return
    from app.services import org_service

    target = scan.target
    user = org_service.billing_user(db, target.organization)
    counts = _severity_counts(findings) if findings else {}
    total = len(findings) if findings else 0

    notifications.notify_scan_finished(
        # PR scans already report in the pull request itself, so skip email.
        email_to=None if _is_pr_scan(scan) else user.email,
        slack_webhook_url=user.slack_webhook_url,
        repo_name=target.name,
        status=status,
        total=total,
        counts=counts,
        report_url=_report_url(scan),
    )


def _start_pr_check(db, scan: Scan, token: str) -> None:
    """Open an in-progress check run so the PR shows Aegis is running."""
    try:
        check_run_id = github_app.create_check_run(
            token, scan.target.name, scan.github_commit_sha
        )
        if check_run_id:
            scan.github_check_run_id = check_run_id
            db.commit()
    except Exception:  # noqa: BLE001 - feedback must never break the scan
        logger.exception("Failed to open check run for scan %s", scan.id)


def _report_pr_result(
    db, scan: Scan, target: Target, findings: list[strix_report.ParsedFinding]
) -> None:
    """Comment on the PR and complete the check run, blocking only on new findings."""
    try:
        counts = _severity_counts(findings)
        total = len(findings)
        token = github_app.get_installation_token(scan.github_installation_id)
        repo_full = target.name

        # Decide from the persisted rows, which carry the fingerprints the
        # diff is computed over — the parsed findings do not have them.
        persisted = list(scan.vulnerabilities)
        diff = triage_service.diff_against_previous(db, scan)
        decision = gate.decide(
            persisted,
            target=target,
            new_fingerprints=set(diff.new_fingerprints),
            has_baseline=diff.has_baseline,
        )

        body = github_app.format_findings_comment(
            counts,
            persisted,
            total=total,
            report_url=_report_url(scan),
            decision=decision,
            new_fingerprints=set(diff.new_fingerprints),
        )
        github_app.upsert_pr_comment(token, repo_full, scan.github_pr_number, body)

        if scan.github_check_run_id:
            title, summary = github_app.check_summary_for(decision, counts)
            github_app.update_check_run(
                token,
                repo_full,
                scan.github_check_run_id,
                conclusion=decision.conclusion,
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
            scan.target.name,
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
    workdir.mkdir(parents=True, exist_ok=True)
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


def _persist_findings(
    db,
    scan: Scan,
    target: Target,
    findings: list[strix_report.ParsedFinding],
    commit_sha: Optional[str],
    model: Optional[str],
) -> None:
    """Store findings, each with the evidence that lets a human verify it."""
    observed = _now()
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
                suggested_fix=f.suggested_fix,
                # What was actually observed — redacted and bounded. Without
                # this a finding is an assertion; with it, it is a receipt.
                evidence=evidence_service.build(
                    f.evidence,
                    engine="Strix",
                    model=model,
                    target_url=target.live_url,
                    commit_sha=commit_sha,
                    observed_at=observed,
                ),
                # Identity that survives re-scans, so this finding can be
                # diffed and triaged against future runs.
                fingerprint=finding_identity.fingerprint(
                    title=f.title,
                    file_path=f.file_path,
                    classification=f.owasp_category,
                ),
            )
        )
    db.flush()
    db.commit()


def _store_attack_chains(db, scan: Scan) -> None:
    """Compose the findings into chains and store them on the scan.

    Suppressed findings are excluded: chaining something a human already
    dismissed would resurrect it at a higher severity through the back door.
    """
    try:
        triage = triage_service.triage_map(db, scan.target_id)
        live = [
            v
            for v in scan.vulnerabilities
            if not (
                v.fingerprint
                and v.fingerprint in triage
                and triage[v.fingerprint].status in triage_service.SUPPRESSED_STATUSES
            )
        ]
        chains = attack_paths.build_chains(live)
        scan.attack_chains = attack_paths.serialize(chains) or None
        db.commit()
        if chains:
            logger.info("Scan %s: %d attack chain(s) identified", scan.id, len(chains))
    except Exception:  # noqa: BLE001 - chaining is analysis, not the report
        logger.warning("Could not compute attack chains for %s", scan.id, exc_info=True)
        db.rollback()


def _record_retest_result(
    db,
    scan: Scan,
    target: Target,
    findings: list[strix_report.ParsedFinding],
    model: Optional[str],
    commit_sha: Optional[str],
) -> None:
    """Turn a completed retest into a verdict on the finding it re-checked."""
    fingerprint = scan.retest_fingerprint or ""
    if not fingerprint:
        return

    reported = {
        finding_identity.fingerprint(
            title=f.title, file_path=f.file_path, classification=f.owasp_category
        )
        for f in findings
    }
    outcome = retest_service.decide_outcome(
        completed=True, reported_fingerprints=reported, fingerprint=fingerprint
    )
    still_there = next(
        (v for v in scan.vulnerabilities if v.fingerprint == fingerprint), None
    )
    triage_service.record_retest(
        db,
        target_id=target.id,
        fingerprint=fingerprint,
        outcome=outcome,
        scan_id=scan.id,
        evidence=retest_service.build_evidence(
            outcome,
            scan_id=scan.id,
            finding=still_there,
            engine="Strix",
            model=model,
            target_url=target.live_url,
            commit_sha=commit_sha,
        ),
    )
    scan.retest_outcome = outcome
    db.commit()
    logger.info("Retest %s for %s: %s", scan.id, fingerprint[:12], outcome.value)


def _mark_retest_inconclusive(db, scan_id: str) -> None:
    """A retest that could not run proves nothing — say so, never "fixed".

    This is the failure mode that would cost the product its credibility: a
    tool that reports a vulnerability as remediated because it crashed before
    checking is worse than one that reports nothing at all.
    """
    db.rollback()
    scan = db.get(Scan, uuid.UUID(scan_id))
    if scan is None or not scan.is_retest or not scan.retest_fingerprint:
        return
    try:
        triage_service.record_retest(
            db,
            target_id=scan.target_id,
            fingerprint=scan.retest_fingerprint,
            outcome=RetestOutcome.INCONCLUSIVE,
            scan_id=scan.id,
            evidence=retest_service.build_evidence(
                RetestOutcome.INCONCLUSIVE,
                scan_id=scan.id,
                error=scan.error_message,
            ),
        )
        scan.retest_outcome = RetestOutcome.INCONCLUSIVE
        db.commit()
    except Exception:  # noqa: BLE001
        logger.warning("Could not record inconclusive retest for %s", scan_id, exc_info=True)
        db.rollback()


def _record_usage(db, scan_id: str, workdir: Path, model: Optional[str]) -> None:
    """Persist the run's LLM spend before the working directory is deleted.

    Called from the task's ``finally``, so it covers every way a scan can end.
    A run that burned tokens and *then* failed still cost real money, and spend
    that is never recorded never shows up against the revenue it was meant to
    earn — the failures are exactly the scans worth counting.

    Best-effort throughout: it re-fetches on a clean session (the failure paths
    arrive with a poisoned one), and swallows its own errors so accounting can
    neither fail a completed scan nor mask the error that ended a failed one.
    A run that never reached Strix has no usage to read, and leaves the columns
    NULL rather than writing a zero that would read as "cost us nothing".
    """
    try:
        db.rollback()
        scan = db.get(Scan, uuid.UUID(scan_id))
        if scan is None:
            return
        scan.engine_model = model
        usage = scan_progress.read_progress(workdir)
        scan.cost_usd = usage.cost_usd
        scan.llm_requests = usage.llm_requests or None
        scan.input_tokens = usage.input_tokens or None
        scan.output_tokens = usage.output_tokens or None
        db.commit()
    except Exception:  # noqa: BLE001 - accounting is not worth failing a scan
        logger.warning("Could not record LLM usage for scan %s", scan_id, exc_info=True)
        db.rollback()


def _fail(db, scan_id: str, message: str) -> None:
    """Mark a scan ``failed`` on a clean session, tolerating a poisoned one."""
    db.rollback()
    scan = db.get(Scan, uuid.UUID(scan_id))
    if scan is None:
        return
    scan.status = ScanStatus.FAILED
    scan.completed_at = _now()
    scan.error_message = _truncate_error(message)
    db.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)


@celery.task(name="app.workers.tasks.enqueue_due_scheduled_scans", bind=True)
def enqueue_due_scheduled_scans(self) -> dict:
    """Beat tick: dispatch a scan for every schedule that is due.

    For each due schedule we advance ``next_run_at`` first (so a transient
    error can't cause a tight re-dispatch loop), then enqueue a scan — but only
    if the organization is still entitled (verified email + active subscription
    within quota). Un-entitled schedules are skipped and retried next period.
    """
    # Imported lazily to avoid a circular import (scan_service imports this module).
    from app.services import billing, org_service, scan_service, schedule_service

    db = SessionLocal()
    dispatched = 0
    skipped = 0
    try:
        due = schedule_service.due_schedules(db)
        for schedule in due:
            schedule_service.advance_after_dispatch(db, schedule)

            target = schedule.target
            org = target.organization
            payer = org_service.billing_user(db, org)
            if not payer.email_verified or not payer.has_accepted_scan_terms:
                skipped += 1
                continue
            try:
                billing.assert_can_create_scan(db, org, scan_mode=schedule.scan_mode)
            except billing.PaymentRequiredError:
                skipped += 1
                continue

            scan_service.create_scan(
                db,
                org=org,
                actor=None,
                target_id=target.id,
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


@celery.task(name="app.workers.tasks.run_asset_discovery", bind=True)
def run_asset_discovery(self) -> dict:
    """Beat tick: enumerate the attack surface of discovery-enabled targets.

    Newly found hosts are recorded as targets in their own right — discovered
    rather than typed in, which is the whole point — and the organization is
    notified. They are *not* scanned automatically: pointing exploits at a host
    nobody has confirmed is theirs is exactly what the authorization gate
    exists to prevent.
    """
    from datetime import timedelta

    from sqlalchemy import select

    from app.services import asm

    if not settings.ASM_ENABLED:
        return {"skipped": "disabled"}

    db = SessionLocal()
    swept = 0
    found = 0
    try:
        cutoff = _now() - timedelta(hours=settings.ASM_INTERVAL_HOURS)
        targets = list(
            db.execute(
                select(Target).where(
                    Target.discovery_enabled.is_(True),
                    Target.url.is_not(None),
                )
            )
            .scalars()
            .all()
        )
        for target in targets:
            # updated_at doubles as "last swept": discovery writes to the row
            # whenever it finds something, and a target nobody has touched in
            # the interval is due either way.
            if target.updated_at and target.updated_at > cutoff:
                continue
            swept += 1
            found += _sweep_target(db, target)

        if swept:
            logger.info("Asset discovery: %d target(s) swept, %d new asset(s)", swept, found)
        return {"swept": swept, "discovered": found}
    except Exception:  # noqa: BLE001 - a beat tick must never crash the worker
        logger.exception("run_asset_discovery failed")
        db.rollback()
        return {"swept": swept, "discovered": found, "error": True}
    finally:
        db.close()


def _sweep_target(db, target: Target) -> int:
    """Discover and record new hosts under one target's domain."""
    from app.services import asm, target_service

    org = target.organization
    known = [t.url or t.name for t in target_service.list_targets(db, org)]
    try:
        hosts = asm.discover(target.url or "", known_hosts=known)
    except asm.DiscoveryError as exc:
        logger.info("Discovery for %s skipped: %s", target.name, exc)
        return 0

    created = 0
    for host in hosts:
        try:
            new_target = target_service.create_target(
                db,
                org=org,
                creator=None,
                kind=TargetKind.WEB,
                values={
                    "name": host.hostname,
                    "url": host.url or f"https://{host.hostname}",
                    "discovered_from_id": target.id,
                },
            )
        except Exception:  # noqa: BLE001 - one bad host must not stop the sweep
            logger.warning("Could not record discovered host %s", host.hostname, exc_info=True)
            db.rollback()
            continue
        created += 1
        audit_service.record(
            db,
            organization_id=org.id,
            action=audit_service.TARGET_DISCOVERED,
            subject_type="target",
            subject_id=new_target.id,
            detail={
                "hostname": host.hostname,
                "status_code": host.status_code,
                "title": host.title,
                "discovered_from": str(target.id),
            },
        )

    if created:
        _notify_discovery(db, org, target, hosts)
    return created


def _notify_discovery(db, org, source: Target, hosts: list) -> None:
    """Tell the organization what appeared, best-effort."""
    from app.services import org_service

    try:
        payer = org_service.billing_user(db, org)
        names = ", ".join(h.hostname for h in hosts[:10])
        notifications.notify_assets_discovered(
            email_to=payer.email,
            slack_webhook_url=payer.slack_webhook_url,
            source_name=source.name,
            hostnames=[h.hostname for h in hosts],
            summary=names,
            dashboard_url=f"{settings.DASHBOARD_URL}/targets",
        )
    except Exception:  # noqa: BLE001
        logger.warning("Could not notify discovery for org %s", org.id, exc_info=True)
