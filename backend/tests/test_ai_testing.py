"""AI-layer testing: the instruction built for LLM and MCP targets."""
from __future__ import annotations

import pytest

from app.models.enums import TargetKind
from app.services import ai_testing


def test_only_ai_kinds_are_supported() -> None:
    assert ai_testing.supports(TargetKind.LLM)
    assert ai_testing.supports(TargetKind.MCP)
    assert not ai_testing.supports(TargetKind.WEB)
    assert not ai_testing.supports(TargetKind.REPO)


def test_llm_instruction_covers_the_owasp_classes() -> None:
    text = ai_testing.build_instruction(
        TargetKind.LLM, target_url="https://app.test/chat"
    )
    for code in ("LLM01", "LLM02", "LLM06", "LLM07"):
        assert code in text
    # Prompt injection tops the list, so it must actually be probed.
    assert "Indirect injection" in text
    assert "https://app.test/chat" in text


def test_mcp_instruction_covers_the_mcp_classes() -> None:
    text = ai_testing.build_instruction(TargetKind.MCP, target_url="https://mcp.test")
    for code in ("MCP01", "MCP02", "MCP03"):
        assert code in text
    # Agent classes apply to an MCP server too — it is what the agent calls.
    assert "ASI02" in text


def test_evidence_rules_keep_model_weirdness_out_of_the_report() -> None:
    """Without this the run returns "the chatbot said something unusual",
    which is exactly the noise this market already complains about."""
    text = ai_testing.build_instruction(TargetKind.LLM, target_url="https://x.test")
    assert "concrete security consequence" in text
    assert "hallucinated facts" in text
    assert "exact prompt sent" in text
    assert "Re-run each successful probe" in text


def test_safety_rules_are_present() -> None:
    text = ai_testing.build_instruction(TargetKind.MCP, target_url="https://x.test")
    assert "do not issue destructive tool calls" in text.lower()


def test_auth_and_custom_instructions_are_included() -> None:
    text = ai_testing.build_instruction(
        TargetKind.LLM,
        target_url="https://x.test",
        auth_notes='header "X-Key: abc"',
        custom_instructions="Focus on the support assistant.",
    )
    assert "X-Key: abc" in text
    assert "Focus on the support assistant." in text


def test_non_ai_kind_is_rejected() -> None:
    with pytest.raises(ValueError):
        ai_testing.build_instruction(TargetKind.WEB, target_url="https://x.test")
