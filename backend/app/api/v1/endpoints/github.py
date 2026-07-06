"""GitHub App endpoints: installation linking + the pull_request webhook."""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.enums import ScanMode, ScanTrigger
from app.models.repository import Repository
from app.models.user import User
from app.schemas.github import (
    GitHubAppInfo,
    InstallationClaimRequest,
    InstallationRead,
)
from app.services import (
    billing,
    github_app,
    installation_service,
    repo_service,
    scan_service,
)

logger = logging.getLogger("aegis.github")

router = APIRouter(prefix="/github", tags=["github"])

# PR checks run in quick mode for fast CI feedback.
_PR_SCAN_MODE = ScanMode.QUICK
_PR_ACTIONS = {"opened", "synchronize", "reopened"}


# --- Installation management ---------------------------------------------
@router.get("/app", response_model=GitHubAppInfo)
def github_app_info(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> GitHubAppInfo:
    """App configuration + the current user's linked installations."""
    return GitHubAppInfo(
        configured=github_app.is_configured(),
        install_url=github_app.install_url(),
        installations=installation_service.list_installations(db, current_user),
    )


@router.post(
    "/installations", response_model=InstallationRead, status_code=status.HTTP_201_CREATED
)
def claim_installation(
    payload: InstallationClaimRequest,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> InstallationRead:
    """Link a GitHub App installation to the signed-in user (post-install)."""
    try:
        account_login = github_app.get_installation_account(payload.installation_id)
    except github_app.GitHubAppError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))

    installation, error = installation_service.claim_installation(
        db, current_user, payload.installation_id, account_login
    )
    if error == "taken":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This installation is already linked to another account",
        )
    return installation


@router.delete("/installations/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_installation(
    record_id: uuid.UUID,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """Unlink a GitHub App installation from the account."""
    installation = installation_service.get_installation(db, record_id, current_user)
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
        return  # installation not linked to any Aegis account
    user = installation.user

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
    repo = repo_service.get_by_github_id(db, user, gh_repo_id)
    if repo is None:
        repo = Repository(
            user_id=user.id, github_repo_id=gh_repo_id, name=full_name, url=html_url
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

    # Respect the same gates as manual scans; skip (don't error) if unentitled.
    if not user.email_verified:
        logger.info("Skipping PR scan for %s: email unverified", full_name)
        return
    try:
        billing.assert_can_create_scan(db, user)
    except billing.PaymentRequiredError as exc:
        logger.info("Skipping PR scan for %s: %s", full_name, exc.reason)
        return

    scan_service.create_scan(
        db,
        user=user,
        repository_id=repo.id,
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
