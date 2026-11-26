"""Generator settings, loaded from environment variables (12-Factor config).

Precedence, highest first: values passed in code > environment variables >
the repo-root `.env` file (shared with the inbox) > the defaults below.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    # The shared .env also holds the inbox's settings: ignore keys we don't use
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-haiku-5-5"
    ai_timeout_seconds: int = Field(default=30, gt=0)

    # Where to deliver generated emails. Dev: the inbox started with uvicorn;
    # Docker sets http://backend:8000 (the service name on the Docker network).
    inbox_url: str = "http://localhost:8000"
    inbox_timeout_seconds: int = Field(default=10, gt=0)
    # Shared secret, the same value as the inbox's INGEST_TOKEN
    ingest_token: SecretStr | None = None

    @field_validator("anthropic_api_key", "ingest_token", mode="before")
    @classmethod
    def blank_secret_means_not_configured(cls, value: object) -> object:
        # `INGEST_TOKEN=` (copied from .env.example) arrives as "": treat as missing
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read once and then cached (use as a FastAPI dependency)."""
    return Settings(_env_file=ENV_FILE)
