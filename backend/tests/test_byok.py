"""BYOK: tier gating, credential selection, and Strix env override."""
from __future__ import annotations

from types import SimpleNamespace

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


def test_byok_credentials_used_when_pro_with_key():
    model, key = tasks._byok_credentials(_user(SubscriptionTier.PRO, "sk-abc"))
    assert (model, key) == ("anthropic/claude-sonnet-4-6", "sk-abc")


def test_byok_credentials_ignored_without_key():
    assert tasks._byok_credentials(_user(SubscriptionTier.PRO, None)) == (None, None)


def test_byok_credentials_ignored_on_starter():
    assert tasks._byok_credentials(_user(SubscriptionTier.STARTER, "sk-abc")) == (None, None)


def test_build_env_uses_override_model_and_key():
    env = strix_runner._build_env("openai/gpt-5", "sk-user")
    assert env["STRIX_LLM"] == "openai/gpt-5"
    assert env["LLM_API_KEY"] == "sk-user"
