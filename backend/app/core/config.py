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

    # --- Encryption (AES-256-GCM for GitHub tokens at rest) --------------
    # Must be a URL-safe base64-encoded 32-byte key. Generate with:
    #   python -c "import os,base64;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
    ENCRYPTION_KEY: str = Field(..., min_length=32)

    # --- GitHub OAuth -----------------------------------------------------
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_OAUTH_REDIRECT_URI: str = ""

    # --- Stripe -----------------------------------------------------------
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # --- LLM providers (passed through to Strix containers) --------------
    STRIX_LLM: str = "openai/gpt-4o"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # --- CORS -------------------------------------------------------------
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] | List[str] = ["http://localhost:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

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
