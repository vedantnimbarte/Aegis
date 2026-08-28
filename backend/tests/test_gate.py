"""The pull-request gate: what blocks a merge, and what only gets reported."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.enums import Severity
from app.services import gate


def _finding(severity: Severity, fingerprint: str):
    return SimpleNamespace(severity=severity, fingerprint=fingerprint, title="x")


def _target(**kwargs):
    return SimpleNamespace(
        gate_fail_severities=kwargs.get("fail", None),
        gate_new_findings_only=kwargs.get("new_only", True),
    )


@pytest.fixture(autouse=True)
def _default_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate.settings, "GITHUB_CHECK_FAIL_SEVERITIES", "critical,high")


def test_clean_scan_passes() -> None:
    decision = gate.decide([], target=_target())
    assert decision.conclusion == "success"
    assert "No exploitable vulnerabilities" in decision.summary()


def test_new_critical_blocks() -> None:
    findings = [_finding(Severity.CRITICAL, "aaa")]
    decision = gate.decide(
        findings, target=_target(), new_fingerprints={"aaa"}, has_baseline=True
    )
    assert decision.blocked is True
    assert decision.blocking_count == 1


def test_pre_existing_critical_does_not_block() -> None:
    """The rule that makes the gate survivable.

    A team turning on scanning inherits whatever their codebase already had.
    A check that fails on that backlog gets switched off in week two, which
    costs more security than it ever bought.
    """
    findings = [_finding(Severity.CRITICAL, "old")]
    decision = gate.decide(
        findings, target=_target(), new_fingerprints=set(), has_baseline=True
    )
    assert decision.blocked is False
    assert decision.total_count == 1
    assert "pre-existing" in decision.summary()


def test_first_scan_treats_everything_as_new() -> None:
    # With no baseline there is no backlog to grandfather in yet.
    findings = [_finding(Severity.HIGH, "aaa")]
    decision = gate.decide(
        findings, target=_target(), new_fingerprints=set(), has_baseline=False
    )
    assert decision.blocked is True


def test_new_findings_only_can_be_turned_off() -> None:
    findings = [_finding(Severity.CRITICAL, "old")]
    decision = gate.decide(
        findings,
        target=_target(new_only=False),
        new_fingerprints=set(),
        has_baseline=True,
    )
    assert decision.blocked is True


def test_low_severity_never_blocks_by_default() -> None:
    findings = [_finding(Severity.LOW, "a"), _finding(Severity.MEDIUM, "b")]
    decision = gate.decide(
        findings, target=_target(), new_fingerprints={"a", "b"}, has_baseline=True
    )
    assert decision.blocked is False


def test_target_policy_overrides_the_platform_default() -> None:
    findings = [_finding(Severity.MEDIUM, "a")]
    decision = gate.decide(
        findings,
        target=_target(fail="medium"),
        new_fingerprints={"a"},
        has_baseline=True,
    )
    assert decision.blocked is True


def test_empty_policy_means_never_block() -> None:
    """A legacy service set to warn-only is a real choice, not an unset field."""
    findings = [_finding(Severity.CRITICAL, "a")]
    decision = gate.decide(
        findings, target=_target(fail=""), new_fingerprints={"a"}, has_baseline=True
    )
    assert decision.blocked is False


def test_no_target_falls_back_to_the_platform_default() -> None:
    assert gate.fail_severities_for(None) == {"critical", "high"}
