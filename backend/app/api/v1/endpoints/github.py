"""GitHub App endpoints: installation linking + the pull_request webhook."""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import Principal
from app.db.session import get_db
from app.models.enums import GitProvider, ScanMode, ScanTrigger, TargetKind
from app.schemas.github import (
    GitHubAppInfo,
    InstallationClaimRequest,
    InstallationRead,
)
from app.services import (
    billing,
    github_app,
    installation_service,
    org_service,
    scan_service,
    target_service,
)

logger = logging.getLogger("aegis.github")

router = APIRouter(prefix="/github", tags=["github"])

# PR checks run in quick mode for fast CI feedback.
_PR_SCAN_MODE = ScanMode.QUICK
_PR_ACTIONS = {"opened", "synchronize", "reopened"}


# --- Installation management ---------------------------------------------
@router.get("/app", response_model=GitHubAppInfo)
def github_app_info(
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> GitHubAppInfo:
    """App configuration + the organization's linked installations."""
    return GitHubAppInfo(
        configured=github_app.is_configured(),
        install_url=github_app.install_url(),
        installations=installation_service.list_installations(
            db, principal.organization
        ),
    )


@router.post(
    "/installations", response_model=InstallationRead, status_code=status.HTTP_201_CREATED
)
def claim_installation(
    payload: InstallationClaimRequest,
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
) -> InstallationRead:
    """Link a GitHub App installation to the organization (post-install).

    Admin-only, and the installation belongs to the organization rather than
    the person who clicked: pull-request scanning must keep working after they
    leave.
    """
    try:
        account_login = github_app.get_installation_account(payload.installation_id)
    except github_app.GitHubAppError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))

    installation, error = installation_service.claim_installation(
        db,
        principal.organization,
        payload.installation_id,
        account_login,
        claimed_by=principal.user,
    )
    if error == "taken":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This installation is already linked to another organization",
        )
    return installation


@router.delete("/installations/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_installation(
    record_id: uuid.UUID,
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
):
    """Unlink a GitHub App installation from the organization."""
    installation = installation_service.get_installation(
        db, record_id, principal.organization
    )
    if installation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Installation not found")
    installation_service.delete_installation(db, installation)


# --- Webhook --------------------------------------------------------------
@router.post("/webhook", include_in_schema=False)
async def github_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Receive App webhooks (signature-verified) and route pull_request events."""
    payload_bytes = await request.body()
    signature = request.headers.get("x-hub-signature-256")
    if not github_app.verify_webhook_signature(payload_bytes, signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    event = request.headers.get("x-github-event", "")
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid payload")

    # Never 500 on a handled event — GitHub would retry indefinitely.
    try:
        if event == "pull_request":
            _process_pull_request(db, payload)
        elif event == "installation":
            _process_installation(db, payload)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to process GitHub webhook event %r", event)

    return {"received": True}


def _process_pull_request(db: Session, payload: dict) -> None:
    if payload.get("action") not in _PR_ACTIONS:
        return

    installation_id = str((payload.get("installation") or {}).get("id") or "")
    installation = installation_service.get_by_installation_id(db, installation_id)
    if installation is None:
        return  # installation not linked to any Aegis organization
    org = installation.organization
    payer = org_service.billing_user(db, org)

    repo_info = payload.get("repository") or {}
    gh_repo_id = str(repo_info.get("id") or "")
    full_name = repo_info.get("full_name")
    html_url = repo_info.get("html_url")

    pr = payload.get("pull_request") or {}
    pr_number = pr.get("number")
    head_sha = (pr.get("head") or {}).get("sha")
    if not (gh_repo_id and full_name and pr_number and head_sha):
        return

    # Find or auto-connect the repository (a PR install implies intent to scan).
    target = target_service.get_by_external_repo(
        db, org, GitProvider.GITHUB, gh_repo_id
    )
    if target is None:
        target = target_service.create_target(
            db,
            org=org,
            creator=None,
            kind=TargetKind.REPO,
            values={
                "provider": GitProvider.GITHUB,
                "external_repo_id": gh_repo_id,
                "name": full_name,
                "clone_url": html_url,
            },
        )

    # Respect the same gates as manual scans; skip (don't error) if unentitled.
    if not payer.email_verified or not payer.has_accepted_scan_terms:
        logger.info("Skipping PR scan for %s: owner not cleared to scan", full_name)
        return
    try:
        billing.assert_can_create_scan(db, org, scan_mode=_PR_SCAN_MODE)
    except billing.PaymentRequiredError as exc:
        logger.info("Skipping PR scan for %s: %s", full_name, exc.reason)
        return

    scan_service.create_scan(
        db,
        org=org,
        actor=None,
        target_id=target.id,
        scan_mode=_PR_SCAN_MODE,
        trigger=ScanTrigger.PULL_REQUEST,
        github_installation_id=installation_id,
        github_pr_number=int(pr_number),
        github_commit_sha=str(head_sha),
    )
    logger.info("Dispatched PR scan for %s #%s", full_name, pr_number)


def _process_installation(db: Session, payload: dict) -> None:
    if payload.get("action") != "deleted":
        return
    installation_id = str((payload.get("installation") or {}).get("id") or "")
    record = installation_service.get_by_installation_id(db, installation_id)
    if record is not None:
        installation_service.delete_installation(db, record)
