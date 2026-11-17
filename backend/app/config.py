"""Application settings, loaded from environment variables (12-Factor config).

Precedence, highest first: values passed in code > environment variables >
the repo-root `.env` file > the defaults below. In Docker, compose injects the
variables, so no `.env` file exists inside the container.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved from this file's location, not the current directory, so the
# repo-root .env is found even when uvicorn runs from backend/.
# (In Docker this points at /.env, which doesn't exist and is simply skipped.)
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    # `.env` also holds settings for later epics; ignore keys we don't model yet
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = "sqlite:///./data/app.db"  # path is fixed in story 1.2

    # Optional: the app must start without it. SecretStr prints as '**********'.
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-haiku-5-5"
    ai_timeout_seconds: int = Field(default=30, gt=0)

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def blank_key_means_not_configured(cls, value: object) -> object:
        # `ANTHROPIC_API_KEY=` (copied from .env.example) arrives as "" — treat as missing
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read once and then cached (use as a FastAPI dependency)."""
    return Settings(_env_file=ENV_FILE)
