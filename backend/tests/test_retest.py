"""Retest: the instruction, and the rule for reading its result."""
from __future__ import annotations

from types import SimpleNamespace

from app.models.enums import RetestOutcome
from app.services import retest


def test_instruction_carries_the_poc_and_forbids_a_wider_survey() -> None:
    text = retest.build_instruction(
        title="SQL injection in the login form",
        fingerprint="abc123",
        description="User input reaches the query unparameterized.",
        poc_code="curl -d \"u=' OR 1=1 --\" https://app.test/login",
        file_path="app/db.py:42",
        target_url="https://app.test",
    )
    assert "SQL injection in the login form" in text
    assert "OR 1=1" in text
    assert "app/db.py:42" in text
    assert "https://app.test" in text
    # It must not turn back into a general assessment.
    assert "do not survey" in text.lower()
    # And it must not accept "the code looks fixed" as proof.
    assert "looks corrected is not evidence" in text


def test_instruction_survives_a_finding_with_no_poc() -> None:
    text = retest.build_instruction(title="Missing rate limit", fingerprint="x")
    assert "Missing rate limit" in text


def test_long_poc_is_clipped() -> None:
    text = retest.build_instruction(
        title="t", fingerprint="f", poc_code="A" * 20_000
    )
    assert "truncated" in text
    assert len(text) < 12_000


def test_exploit_reproduces_means_still_vulnerable() -> None:
    outcome = retest.decide_outcome(
        completed=True, reported_fingerprints={"abc"}, fingerprint="abc"
    )
    assert outcome is RetestOutcome.STILL_VULNERABLE


def test_exploit_gone_means_fixed() -> None:
    outcome = retest.decide_outcome(
        completed=True, reported_fingerprints=set(), fingerprint="abc"
    )
    assert outcome is RetestOutcome.FIXED


def test_other_findings_do_not_count_as_this_one() -> None:
    outcome = retest.decide_outcome(
        completed=True, reported_fingerprints={"zzz"}, fingerprint="abc"
    )
    assert outcome is RetestOutcome.FIXED


def test_a_run_that_did_not_complete_is_never_fixed() -> None:
    """The failure mode that would cost the product its credibility.

    Reporting a vulnerability as remediated because the retest crashed before
    checking is worse than reporting nothing at all.
    """
    outcome = retest.decide_outcome(
        completed=False, reported_fingerprints=set(), fingerprint="abc"
    )
    assert outcome is RetestOutcome.INCONCLUSIVE


def test_evidence_for_a_fix_records_provenance() -> None:
    bundle = retest.build_evidence(
        RetestOutcome.FIXED,
        scan_id="11111111-1111-1111-1111-111111111111",
        engine="Strix",
        model="openai/gpt-4o",
        target_url="https://app.test",
        commit_sha="deadbeef",
    )
    assert bundle["outcome"] == "fixed"
    assert bundle["commit_sha"] == "deadbeef"
    assert "verified_at" in bundle


def test_evidence_for_a_still_vulnerable_finding_carries_the_fresh_observation() -> None:
    finding = SimpleNamespace(
        evidence={"request": "GET /admin", "response": "200 OK", "poc_output": "pwned"}
    )
    bundle = retest.build_evidence(
        RetestOutcome.STILL_VULNERABLE, scan_id="s", finding=finding
    )
    assert bundle["request"] == "GET /admin"
    assert bundle["poc_output"] == "pwned"


def test_inconclusive_evidence_says_why() -> None:
    bundle = retest.build_evidence(
        RetestOutcome.INCONCLUSIVE, scan_id="s", error="target unreachable"
    )
    assert bundle["error"] == "target unreachable"


def test_summarize_reads_as_a_sentence() -> None:
    assert "no longer works" in retest.summarize(RetestOutcome.FIXED, None)
    assert retest.summarize(None, None) == "Not retested"
