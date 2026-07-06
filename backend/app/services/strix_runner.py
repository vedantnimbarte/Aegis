"""Drive the Strix CLI and locate its output.

Strix is a Python CLI (installed from the ``strix-agent`` package) that runs
in headless mode and spawns its own Docker sandbox containers via the host
Docker socket — so the worker must have the socket mounted (see
docker-compose.yml). We invoke it as a subprocess, let it auto-name the run,
then hand the resulting ``strix_runs/<run>/`` directory to the report parser.

Command (see specs §4 and the Strix CLI docs):
    strix -n --target <repo> --scan-mode <quick|standard|deep> \
          [--instruction "<text>"] [--max-budget-usd <n>]

Exit codes: ``0`` = completed, no vulnerabilities; ``2`` = completed, findings
present. Both are success. Anything else is a genuine failure.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from app.core.config import settings

# Strix writes every run under this directory (relative to its cwd).
RUNS_DIR_NAME = "strix_runs"

# Exit codes Strix uses to signal a successful run.
_SUCCESS_EXIT_CODES = frozenset({0, 2})

# Keep the tail of Strix's output for diagnosing failures without storing MBs.
_ERROR_OUTPUT_CHARS = 4000


class StrixError(Exception):
    """Raised when the Strix engine cannot run or complete."""


def run_strix(
    *,
    target_dir: Path,
    scan_mode: str,
    workdir: Path,
    instruction: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Path:
    """Run a Strix scan against ``target_dir`` and return its run directory.

    ``workdir`` is used as the process cwd; Strix creates ``strix_runs/`` under
    it, so a fresh per-scan ``workdir`` yields exactly one run directory to
    locate afterwards.
    """
    api_key = settings.strix_llm_api_key
    if not api_key:
        raise StrixError(
            "No LLM API key configured for Strix. Set LLM_API_KEY (or the "
            "provider key matching STRIX_LLM)."
        )

    workdir.mkdir(parents=True, exist_ok=True)
    cmd = _build_command(target_dir=target_dir, scan_mode=scan_mode, instruction=instruction)
    env = _build_env(api_key)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workdir),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout or settings.STRIX_SCAN_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise StrixError(
            f"Strix executable '{settings.STRIX_BIN}' not found on the worker"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise StrixError(
            f"Strix scan timed out after {exc.timeout:.0f}s"
        ) from exc

    if proc.returncode not in _SUCCESS_EXIT_CODES:
        tail = (proc.stderr or proc.stdout or "").strip()[-_ERROR_OUTPUT_CHARS:]
        raise StrixError(
            f"Strix exited with code {proc.returncode}: {tail or 'no output'}"
        )

    return _locate_run_dir(workdir)


def _build_command(
    *, target_dir: Path, scan_mode: str, instruction: Optional[str]
) -> list[str]:
    cmd = [
        settings.STRIX_BIN,
        "--non-interactive",
        "--target",
        str(target_dir),
        "--scan-mode",
        scan_mode,
    ]
    if instruction and instruction.strip():
        cmd += ["--instruction", instruction.strip()]
    if settings.STRIX_MAX_BUDGET_USD:
        cmd += ["--max-budget-usd", str(settings.STRIX_MAX_BUDGET_USD)]
    return cmd


def _build_env(api_key: str) -> dict[str, str]:
    """Inherit the ambient env (incl. DOCKER_HOST) and add Strix's config."""
    env = os.environ.copy()
    env["STRIX_LLM"] = settings.STRIX_LLM
    env["LLM_API_KEY"] = api_key
    if settings.PERPLEXITY_API_KEY:
        env["PERPLEXITY_API_KEY"] = settings.PERPLEXITY_API_KEY
    if settings.STRIX_REASONING_EFFORT:
        env["STRIX_REASONING_EFFORT"] = settings.STRIX_REASONING_EFFORT
    return env


def _locate_run_dir(workdir: Path) -> Path:
    """Find the single run directory Strix created under ``workdir``.

    Strix auto-names runs (there is no flag to set the name), so we discover
    it. With a fresh per-scan ``workdir`` there is exactly one; if several
    exist we take the most recently modified.
    """
    runs_root = workdir / RUNS_DIR_NAME
    if not runs_root.is_dir():
        raise StrixError(
            f"Strix produced no '{RUNS_DIR_NAME}' output directory under {workdir}"
        )

    run_dirs = [p for p in runs_root.iterdir() if p.is_dir()]
    if not run_dirs:
        raise StrixError(f"Strix produced no run directory under {runs_root}")

    return max(run_dirs, key=lambda p: p.stat().st_mtime)
