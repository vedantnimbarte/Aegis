"""Read Strix's live run state so the UI can show progress, not just a spinner.

While a scan runs, Strix maintains a few JSON files under
``strix_runs/<run_name>/``:

    run.json          run status, start time, and cumulative ``llm_usage``
    .state/agents.json  agent id -> name / status ("running", "finished", …)
    .state/todos.json   agent id -> todo id -> {title, description, status}

None of it is a documented API, so every read here is best-effort: a missing,
half-written, or reshaped file yields an empty result rather than an error.
The scan itself must never fail because its progress view could not be read.

Framework-free (paths in, plain dicts out) so it can be unit-tested without a
DB or settings, matching ``strix_report``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

RUN_METADATA_FILENAME = "run.json"
STATE_DIRNAME = ".state"
AGENTS_FILENAME = "agents.json"
TODOS_FILENAME = "todos.json"

# Strix marks a todo done by either flag; treat both as complete.
_DONE_STATUSES = frozenset({"completed", "done", "finished"})
_ACTIVE_STATUSES = frozenset({"in_progress", "running", "active"})


@dataclass(frozen=True)
class ProgressStep:
    """One unit of agent work, rendered as a step in the UI."""

    title: str
    detail: Optional[str] = None
    status: str = "pending"  # pending | active | done
    agent: Optional[str] = None


@dataclass(frozen=True)
class ScanProgress:
    """A snapshot of an in-flight Strix run."""

    run_id: Optional[str] = None
    phase: str = "starting"
    steps: list[ProgressStep] = field(default_factory=list)
    agents: list[dict[str, str]] = field(default_factory=list)
    llm_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Optional[float] = None


def _load_json(path: Path) -> Any:
    """Best-effort JSON read; None on any missing/unreadable/partial file."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def find_run_dir(workdir: Path) -> Optional[Path]:
    """Locate the single ``strix_runs/<run>`` directory under a scan workdir.

    Aegis uses a fresh workdir per scan, so there is normally exactly one. If
    several exist, the most recently modified wins.
    """
    runs_root = workdir / "strix_runs"
    try:
        candidates = [p for p in runs_root.iterdir() if p.is_dir()]
    except OSError:
        return None
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _normalize_status(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value in _DONE_STATUSES:
        return "done"
    if value in _ACTIVE_STATUSES:
        return "active"
    return "pending"


def _read_agents(run_dir: Path) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Return (agent summaries, agent id -> display name)."""
    data = _load_json(run_dir / STATE_DIRNAME / AGENTS_FILENAME)
    if not isinstance(data, dict):
        return [], {}

    names = data.get("names") if isinstance(data.get("names"), dict) else {}
    statuses = data.get("statuses") if isinstance(data.get("statuses"), dict) else {}

    name_by_id = {str(k): str(v) for k, v in (names or {}).items()}
    agents = [
        {"name": name_by_id.get(str(agent_id), str(agent_id)), "status": str(status)}
        for agent_id, status in (statuses or {}).items()
    ]
    return agents, name_by_id


def _read_steps(run_dir: Path, name_by_id: dict[str, str]) -> list[ProgressStep]:
    """Flatten Strix's per-agent todo map into an ordered step list."""
    data = _load_json(run_dir / STATE_DIRNAME / TODOS_FILENAME)
    if not isinstance(data, dict):
        return []

    steps: list[ProgressStep] = []
    for agent_id, todos in data.items():
        if not isinstance(todos, dict):
            continue
        agent_name = name_by_id.get(str(agent_id))
        for todo in todos.values():
            if not isinstance(todo, dict):
                continue
            title = str(todo.get("title") or "").strip()
            if not title:
                continue
            detail = str(todo.get("description") or "").strip() or None
            # Strix stamps completed_at even when it leaves `status` alone,
            # so trust the timestamp over the flag.
            status = _normalize_status(todo.get("status"))
            if todo.get("completed_at"):
                status = "done"
            steps.append(
                ProgressStep(
                    title=title, detail=detail, status=status, agent=agent_name
                )
            )
    return steps


def _read_usage(run_dir: Path) -> tuple[Optional[str], str, dict[str, Any]]:
    """Return (run_id, phase, usage) from ``run.json``."""
    data = _load_json(run_dir / RUN_METADATA_FILENAME)
    if not isinstance(data, dict):
        return None, "starting", {}
    usage = data.get("llm_usage")
    return (
        str(data.get("run_id")) if data.get("run_id") else None,
        str(data.get("status") or "running"),
        usage if isinstance(usage, dict) else {},
    )


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def read_progress(workdir: Path) -> ScanProgress:
    """Snapshot the progress of the run under ``workdir`` (never raises)."""
    run_dir = find_run_dir(workdir)
    if run_dir is None:
        # The checkout/sandbox stage runs before Strix creates its run dir.
        return ScanProgress(phase="preparing")

    run_id, phase, usage = _read_usage(run_dir)
    agents, name_by_id = _read_agents(run_dir)
    steps = _read_steps(run_dir, name_by_id)

    # Strix reports spend as ``cost``; the others are defensive aliases.
    cost = usage.get("cost", usage.get("cost_usd", usage.get("total_cost")))
    try:
        cost_usd = float(cost) if cost is not None else None
    except (TypeError, ValueError):
        cost_usd = None

    return ScanProgress(
        run_id=run_id,
        phase=phase,
        steps=steps,
        agents=agents,
        llm_requests=_as_int(usage.get("requests")),
        input_tokens=_as_int(usage.get("input_tokens")),
        output_tokens=_as_int(usage.get("output_tokens")),
        cost_usd=cost_usd,
    )
