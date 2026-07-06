"""Application configuration.

All settings are loaded from environment variables (or a local `.env` file)
using pydantic-settings. Never hard-code secrets — inject them via the
environment (AWS Secrets Manager in production, `.env` locally).
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Core -------------------------------------------------------------
    PROJECT_NAME: str = "Aegis"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False

    # --- Database ---------------------------------------------------------
    # e.g. postgresql+psycopg://aegis:aegis@localhost:5432/aegis
    DATABASE_URL: PostgresDsn

    # --- Redis / Celery ---------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    # --- Auth / JWT -------------------------------------------------------
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Password-reset links expire quickly; the token is also bound to the
    # current password hash, so it becomes invalid the moment the password
    # changes (single-use).
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    # Email-verification links are less sensitive and longer-lived.
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 48

    # --- Email (SMTP) -----------------------------------------------------
    # When SMTP_HOST is blank, emails are logged instead of sent (dev mode).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_STARTTLS: bool = True
    EMAIL_FROM: str = "Aegis Security <no-reply@aegis.security>"

    # --- Encryption (AES-256-GCM for GitHub tokens at rest) --------------
    # Must be a URL-safe base64-encoded 32-byte key. Generate with:
    #   python -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
    ENCRYPTION_KEY: str = Field(..., min_length=32)

    # --- GitHub OAuth -----------------------------------------------------
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_OAUTH_REDIRECT_URI: str = ""

    # --- GitHub App (CI/CD PR scanning) ----------------------------------
    # A separate GitHub App (not the OAuth app) that installs on repos, receives
    # pull_request webhooks, and posts a findings comment + check run.
    GITHUB_APP_ID: str = ""
    GITHUB_APP_SLUG: str = ""  # for the install URL: github.com/apps/<slug>
    # RSA private key (PEM). Accepts a literal PEM, a "\n"-escaped PEM, or a
    # base64-encoded PEM (recommended for single-line env vars).
    GITHUB_APP_PRIVATE_KEY: str = ""
    GITHUB_APP_WEBHOOK_SECRET: str = ""
    # Comma-separated severities that fail the PR check run.
    GITHUB_CHECK_FAIL_SEVERITIES: str = "critical,high"

    # --- Stripe -----------------------------------------------------------
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    # Recurring Price IDs for each self-serve tier (from the Stripe dashboard).
    # Enterprise is sales-led and has no self-serve price.
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_PRO: str = ""
    # Where Stripe Checkout / the billing portal return the user. Points at the
    # dashboard app (see ../dashboard). No trailing slash.
    DASHBOARD_URL: str = "http://localhost:3001"

    # --- LLM providers (passed through to Strix) -------------------------
    # Model id in LiteLLM `provider/model` form, e.g. "openai/gpt-4o" or
    # "anthropic/claude-sonnet-4-6". Consumed by Strix as $STRIX_LLM.
    STRIX_LLM: str = "openai/gpt-4o"
    # Strix authenticates with a single $LLM_API_KEY. If left blank we fall
    # back to the provider-specific key inferred from STRIX_LLM's prefix.
    LLM_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    # Optional: enables Strix's web-search capability.
    PERPLEXITY_API_KEY: str = ""

    # --- Strix engine -----------------------------------------------------
    # Executable name/path of the Strix CLI (installed from `strix-agent`).
    STRIX_BIN: str = "strix"
    # Base directory for per-scan working dirs (repo checkout + strix_runs).
    STRIX_WORK_DIR: str = "/tmp/aegis-scans"
    # Hard wall-clock cap for a single Strix subprocess. Keep below Celery's
    # task_time_limit (see workers/celery_app.py) so we fail the scan cleanly
    # rather than having the worker killed mid-run.
    STRIX_SCAN_TIMEOUT_SECONDS: int = 60 * 60
    # Optional guardrail: cap LLM spend per scan (USD). None = no cap.
    STRIX_MAX_BUDGET_USD: float | None = None
    # Optional: one of none|minimal|low|medium|high|xhigh (Strix default used
    # when blank).
    STRIX_REASONING_EFFORT: str = ""
    # Timeout for the `git clone` of the target repo (seconds).
    GIT_CLONE_TIMEOUT_SECONDS: int = 300

    # --- CORS -------------------------------------------------------------
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] | List[str] = ["http://localhost:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def strix_llm_api_key(self) -> str:
        """The LLM key Strix should authenticate with.

        Prefers the explicit ``LLM_API_KEY``; otherwise infers it from the
        provider prefix of ``STRIX_LLM`` (e.g. ``openai/…`` -> OpenAI key).
        """
        if self.LLM_API_KEY:
            return self.LLM_API_KEY
        provider = self.STRIX_LLM.split("/", 1)[0].lower()
        if provider == "openai":
            return self.OPENAI_API_KEY
        if provider == "anthropic":
            return self.ANTHROPIC_API_KEY
        return ""

    @property
    def celery_broker(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so we parse the environment only once."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
