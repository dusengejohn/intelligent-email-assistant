"""Application settings, loaded from environment variables (12-Factor config).

Precedence, highest first: values passed in code > environment variables >
the repo-root `.env` file > the defaults below. In Docker, compose injects the
variables, so no `.env` file exists inside the container.
"""

import re
from datetime import time
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Paths are resolved from this file's location, not the current directory, so
# the repo-root .env and data/ are found even when uvicorn runs from backend/.
# (In Docker REPO_ROOT is `/`: there is no /.env, so it is simply skipped, and
# docker-compose.yml sets DATABASE_URL to the file inside the data volume.)
REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"
DEFAULT_DATABASE_URL = f"sqlite:///{(REPO_ROOT / 'data' / 'app.db').as_posix()}"

# "09:00-17:00": 24 h clock, two digits each, spaces around the dash allowed
WORK_HOURS_PATTERN = re.compile(
    r"^\s*([01]\d|2[0-3]):([0-5]\d)\s*-\s*([01]\d|2[0-3]):([0-5]\d)\s*$"
)


def _parse_work_hours(value: str) -> tuple[time, time]:
    match = WORK_HOURS_PATTERN.match(value)
    if match is None:
        raise ValueError(f"must look like HH:MM-HH:MM (24 h), e.g. 09:00-17:00; got {value!r}")
    h1, m1, h2, m2 = (int(group) for group in match.groups())
    start, end = time(h1, m1), time(h2, m2)
    if start >= end:
        raise ValueError(f"start must be before end (no shift across midnight); got {value!r}")
    return start, end


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

    # Calendar planning (Epic 4). Kept as plain text and checked by the validators
    # below: pydantic-settings would read richer types from the environment as JSON.
    app_timezone: str = "America/Toronto"  # an IANA name, so DST rules are known
    work_hours: str = "09:00-17:00"  # local time in app_timezone

    @field_validator("ingest_token", mode="before")
    @classmethod
    def blank_secret_means_not_configured(cls, value: object) -> object:
        # `INGEST_TOKEN=` (copied from .env.example) arrives as "" — treat as missing
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("app_timezone")
    @classmethod
    def must_be_a_known_time_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(
                f"must be an IANA time zone such as America/Toronto; got {value!r}"
            ) from None
        return value

    @field_validator("work_hours")
    @classmethod
    def must_be_a_valid_range(cls, value: str) -> str:
        _parse_work_hours(value)  # raises ValueError with a readable message
        return value

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)

    @property
    def work_start(self) -> time:
        return _parse_work_hours(self.work_hours)[0]

    @property
    def work_end(self) -> time:
        return _parse_work_hours(self.work_hours)[1]


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read once and then cached (use as a FastAPI dependency)."""
    return Settings(_env_file=ENV_FILE)
