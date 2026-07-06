"""Check out a target repository for scanning.

Clones the repo (shallow, single-branch) into a local directory that is then
handed to Strix as ``--target``. Private repos are cloned over HTTPS using the
user's GitHub token; the token is injected into the clone URL only and is
scrubbed from any error text so it can never reach logs or the database.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

from app.core.config import settings


class CheckoutError(Exception):
    """Raised when the target repository cannot be checked out."""


def clone_repository(
    repo_url: str,
    dest: Path,
    *,
    github_token: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Path:
    """Shallow-clone ``repo_url`` into ``dest`` and return ``dest``.

    Raises ``CheckoutError`` on any git failure, with the token (if any)
    scrubbed from the message.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    clone_url = _authenticated_url(repo_url, github_token)

    try:
        proc = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--no-tags",
                clone_url,
                str(dest),
            ],
            capture_output=True,
            text=True,
            timeout=timeout or settings.GIT_CLONE_TIMEOUT_SECONDS,
            # Never let git prompt for credentials on a private/bad URL — fail fast.
            env={"GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "PATH": _path()},
        )
    except FileNotFoundError as exc:  # git not installed in the image
        raise CheckoutError("git executable not found on the worker") from exc
    except subprocess.TimeoutExpired as exc:
        raise CheckoutError(
            f"Cloning the repository timed out after {exc.timeout:.0f}s"
        ) from exc

    if proc.returncode != 0:
        detail = _scrub(proc.stderr.strip() or proc.stdout.strip(), github_token)
        raise CheckoutError(f"git clone failed: {detail}")

    return dest


def _authenticated_url(repo_url: str, token: Optional[str]) -> str:
    """Return an HTTPS clone URL with the token embedded, when applicable.

    Only HTTPS URLs are rewritten; SSH/other schemes are returned unchanged.
    Uses the ``x-access-token:<token>`` form GitHub expects for OAuth tokens.
    """
    if not token:
        return repo_url

    parsed = urlparse(repo_url)
    if parsed.scheme != "https":
        return repo_url

    # Strip any existing userinfo, then inject our credentials.
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    netloc = f"x-access-token:{token}@{host}"
    return urlunparse(parsed._replace(netloc=netloc))


def _scrub(text: str, token: Optional[str]) -> str:
    """Remove the token and any embedded credentials from error text."""
    if token:
        text = text.replace(token, "***")
    # Belt-and-suspenders: redact any user:pass@ that slipped through.
    return re.sub(r"//[^/@\s]+:[^/@\s]+@", "//***@", text)


def _path() -> str:
    """Preserve the ambient PATH so the sanitized env can still find git."""
    import os

    return os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")
