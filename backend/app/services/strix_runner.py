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
    scan_mode: str,
    workdir: Path,
    target_dir: Optional[Path] = None,
    instruction: Optional[str] = None,
    instruction_file: Optional[Path] = None,
    extra_targets: Optional[list[str]] = None,
    timeout: Optional[int] = None,
    llm_model: Optional[str] = None,
    llm_api_key: Optional[str] = None,
    max_budget_usd: Optional[float] = None,
) -> Path:
    """Run a Strix scan and return its run directory.

    ``target_dir`` is a source checkout; it is optional because half the
    targets Aegis tests have no repository at all — a live web app, an API, an
    LLM endpoint or an MCP server is addressed entirely by URL. At least one
    of ``target_dir`` or ``extra_targets`` must be given.

    ``extra_targets`` adds further ``--target`` values (e.g. a live app URL for
    grey-box testing). ``instruction_file`` (mutually exclusive with
    ``instruction``) passes ``--instruction-file`` so credentials never appear
    on the command line.

    ``llm_model``/``llm_api_key`` override the platform LLM (BYOK); either or
    both fall back to the shared config when blank. ``max_budget_usd``
    overrides the platform per-scan spend cap for one target.

    ``workdir`` is used as the process cwd; Strix creates ``strix_runs/`` under
    it, so a fresh per-scan ``workdir`` yields exactly one run directory to
    locate afterwards.
    """
    if target_dir is None and not (extra_targets or []):
        raise StrixError("A scan needs at least one target (a checkout or a URL)")
    model = llm_model or settings.STRIX_LLM
    api_key = llm_api_key or settings.strix_llm_api_key
    if not api_key:
        raise StrixError(
            "No LLM API key configured for Strix. Set LLM_API_KEY (or the "
            "provider key matching STRIX_LLM)."
        )

    workdir.mkdir(parents=True, exist_ok=True)
    cmd = _build_command(
        target_dir=target_dir,
        scan_mode=scan_mode,
        instruction=instruction,
        instruction_file=instruction_file,
        extra_targets=extra_targets,
        max_budget_usd=max_budget_usd,
    )
    env = _build_env(model, api_key)

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
    *,
    scan_mode: str,
    target_dir: Optional[Path] = None,
    instruction: Optional[str] = None,
    instruction_file: Optional[Path] = None,
    extra_targets: Optional[list[str]] = None,
    max_budget_usd: Optional[float] = None,
) -> list[str]:
    cmd = [settings.STRIX_BIN, "--non-interactive"]
    if target_dir is not None:
        cmd += ["--target", str(target_dir)]
    for extra in extra_targets or []:
        if extra and extra.strip():
            cmd += ["--target", extra.strip()]
    cmd += ["--scan-mode", scan_mode]

    # --instruction and --instruction-file are mutually exclusive; the file
    # form is used for grey-box so credentials stay off the command line.
    if instruction_file is not None:
        cmd += ["--instruction-file", str(instruction_file)]
    elif instruction and instruction.strip():
        cmd += ["--instruction", instruction.strip()]

    # A per-target cap overrides the platform default, so one expensive
    # monorepo can be bounded without lowering the ceiling everywhere.
    budget = max_budget_usd if max_budget_usd else settings.STRIX_MAX_BUDGET_USD
    if budget:
        cmd += ["--max-budget-usd", str(budget)]
    return cmd


def _build_env(model: str, api_key: str) -> dict[str, str]:
    """Inherit the ambient env (incl. DOCKER_HOST) and add Strix's config."""
    env = os.environ.copy()
    env["STRIX_LLM"] = model
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
