"""BYOK: tier gating, credential selection, and Strix env override."""
from __future__ import annotations

from types import SimpleNamespace

from app.core.config import settings
from app.models.enums import SubscriptionTier
from app.services import billing_plans, strix_runner
from app.workers import tasks


def test_byok_allowed_only_on_pro_and_above():
    assert not billing_plans.limits_for(SubscriptionTier.FREE).byok
    assert not billing_plans.limits_for(SubscriptionTier.STARTER).byok
    assert billing_plans.limits_for(SubscriptionTier.PRO).byok
    assert billing_plans.limits_for(SubscriptionTier.ENTERPRISE).byok


def _user(tier, key, model="anthropic/claude-sonnet-4-6"):
    return SimpleNamespace(subscription_tier=tier, llm_api_key=key, llm_model=model)


def _target_for(monkeypatch, user):
    """A target whose organization bills to ``user``.

    Credentials now resolve through the organization's billing user, so the
    lookup is stubbed rather than the user passed directly.
    """
    org = SimpleNamespace(id="org", owner=user, parent_id=None)
    monkeypatch.setattr(
        "app.services.org_service.billing_user", lambda db, o: user
    )
    return SimpleNamespace(organization=org)


def test_byok_credentials_used_when_pro_with_key(monkeypatch):
    user = _user(SubscriptionTier.PRO, "sk-abc")
    model, key = tasks._llm_credentials(None, _target_for(monkeypatch, user))
    assert (model, key) == ("anthropic/claude-sonnet-4-6", "sk-abc")


def test_platform_model_used_without_a_byok_key(monkeypatch):
    user = _user(SubscriptionTier.PRO, None)
    model, key = tasks._llm_credentials(None, _target_for(monkeypatch, user))
    # The model is still reported so it can be recorded as evidence
    # provenance; only the key falls back to the platform's own.
    assert model == settings.STRIX_LLM
    assert key is None


def test_byok_credentials_ignored_on_starter(monkeypatch):
    user = _user(SubscriptionTier.STARTER, "sk-abc")
    model, key = tasks._llm_credentials(None, _target_for(monkeypatch, user))
    assert model == settings.STRIX_LLM
    assert key is None


def test_build_env_uses_override_model_and_key():
    env = strix_runner._build_env("openai/gpt-5", "sk-user")
    assert env["STRIX_LLM"] == "openai/gpt-5"
    assert env["LLM_API_KEY"] == "sk-user"


def test_per_target_budget_overrides_the_platform_cap():
    cmd = strix_runner._build_command(scan_mode="quick", extra_targets=["https://x.test"], max_budget_usd=2.5)
    assert "--max-budget-usd" in cmd
    assert cmd[cmd.index("--max-budget-usd") + 1] == "2.5"
