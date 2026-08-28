"""The compliance pack: what it states, and what it refuses to claim."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.services import compliance


def _context(**overrides):
    base = dict(
        organization_name="Acme Inc",
        target_name="acme/api",
        target_kind="repo",
        scope_description=compliance.scope_statement("repo", "acme/api"),
        window_start=datetime(2026, 8, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 8, 2, tzinfo=timezone.utc),
        report_id="scan-123",
        findings_total=3,
        open_count=1,
        verified_fixed_count=2,
        counts_by_severity={"critical": 0, "high": 1, "medium": 2},
    )
    base.update(overrides)
    return compliance.ComplianceContext(**base)


def test_scope_statement_names_what_was_tested() -> None:
    assert "acme/api" in compliance.scope_statement("repo", "acme/api")
    assert "Model Context Protocol" in compliance.scope_statement("mcp", "mcp.test")
    assert "LLM-backed" in compliance.scope_statement("llm", "chat.test")


def test_executive_summary_states_the_outcome_and_the_dates() -> None:
    text = compliance.executive_summary(_context())
    assert "3 validated finding" in text
    assert "01 August 2026" in text
    assert "2 finding(s) have since been remediated" in text
    # The claim that separates this from a scanner report.
    assert "validated by exploitation" in text


def test_executive_summary_for_a_clean_scan() -> None:
    text = compliance.executive_summary(
        _context(findings_total=0, open_count=0, verified_fixed_count=0, counts_by_severity={})
    )
    assert "No exploitable vulnerabilities were identified" in text


def test_attestation_letter_states_who_tested_what_and_when() -> None:
    letter = compliance.attestation_letter(
        _context(attestor_name="R. Vega", attestor_title="Head of Security")
    )
    assert "Acme Inc" in letter
    assert "acme/api" in letter
    assert "01 August 2026" in letter
    assert "R. Vega" in letter
    assert "scan-123" in letter


def test_attestation_letter_is_honest_about_being_automated() -> None:
    """Auditors ask. A letter that obscures it fails the question badly."""
    letter = compliance.attestation_letter(_context())
    assert "autonomous agents" in letter


def test_attestation_letter_never_claims_compliance() -> None:
    """No tool can certify SOC 2. Claiming to is how a customer gets burned in
    an audit they trusted us for."""
    letter = compliance.attestation_letter(_context())
    assert "not a certification of compliance" in letter


def test_letter_reports_open_findings_accurately() -> None:
    assert "no findings remain open" in compliance.attestation_letter(
        _context(open_count=0)
    )
    assert "1 finding(s) remain" in compliance.attestation_letter(_context(open_count=1))


def test_control_mappings_are_evidence_toward_not_passes() -> None:
    mappings = compliance.mappings_for()
    frameworks = {m.framework for m in mappings}
    assert any("SOC 2" in f for f in frameworks)
    assert any("ISO" in f for f in frameworks)
    assert all("compliant" not in m.description.lower() for m in mappings)


def test_mappings_can_be_filtered() -> None:
    only = compliance.mappings_for(("SOC 2 (TSC 2017)",))
    assert only and all(m.framework == "SOC 2 (TSC 2017)" for m in only)


def test_limitations_state_that_absence_is_not_proof() -> None:
    joined = " ".join(compliance.LIMITATIONS)
    assert "absence of a finding is not proof" in joined
    assert "not equivalent to a manual engagement" in joined


def test_build_context_reads_a_report() -> None:
    report = SimpleNamespace(
        scan=SimpleNamespace(
            id="abc",
            target_name="shop.test",
            target_kind=SimpleNamespace(value="web"),
            started_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            completed_at=datetime(2026, 8, 1, 2, tzinfo=timezone.utc),
            created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            engine_model="openai/gpt-4o",
        ),
        total=2,
        open_count=2,
        verified_fixed_count=0,
        counts_by_severity={"high": 2},
    )
    context = compliance.build_context(report, organization_name="Acme")
    assert context.target_name == "shop.test"
    assert context.model == "openai/gpt-4o"
    assert "shop.test" in context.scope_description
