"""Application settings, loaded from environment variables (12-Factor config).

Precedence, highest first: values passed in code > environment variables >
the repo-root `.env` file > the defaults below. In Docker, compose injects the
variables, so no `.env` file exists inside the container.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Paths are resolved from this file's location, not the current directory, so
# the repo-root .env and data/ are found even when uvicorn runs from backend/.
# (In Docker REPO_ROOT is `/`: there is no /.env, so it is simply skipped, and
# docker-compose.yml sets DATABASE_URL to the file inside the data volume.)
REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"
DEFAULT_DATABASE_URL = f"sqlite:///{(REPO_ROOT / 'data' / 'app.db').as_posix()}"


class Settings(BaseSettings):
    # `.env` also holds settings for later epics; ignore keys we don't model yet
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = DEFAULT_DATABASE_URL

    # No AI settings: the inbox classifies with keyword rules only (#92). The
    # shared .env's ANTHROPIC_* keys are for the generator and ignored here.

    # Shared secret that other services (the generator) send in the
    # X-Ingest-Token header to deliver emails. Not set = ingest disabled (503).
    ingest_token: SecretStr | None = None

    @field_validator("ingest_token", mode="before")
    @classmethod
    def blank_secret_means_not_configured(cls, value: object) -> object:
        # `INGEST_TOKEN=` (copied from .env.example) arrives as "" — treat as missing
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read once and then cached (use as a FastAPI dependency)."""
    return Settings(_env_file=ENV_FILE)
