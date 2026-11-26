"""Tests for app.config (story 1.1, issue #27; AI settings removed in #92).

The inbox has no AI settings any more (keyword rules only); the reading rules
(.env file, environment wins, secrets hidden) are tested with the settings left.
"""

from pathlib import Path

import pytest

from app import config
from app.config import Settings, get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_values_are_read_from_dotenv_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=from-file\nINGEST_TOKEN=token-from-file\n")
    monkeypatch.setattr(config, "ENV_FILE", env_file)

    settings = get_settings()

    assert settings.app_env == "from-file"
    assert settings.ingest_token is not None
    assert settings.ingest_token.get_secret_value() == "token-from-file"


def test_environment_variable_overrides_dotenv_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_ENV=from-file\n")
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    monkeypatch.setenv("APP_ENV", "from-env")

    assert get_settings().app_env == "from-env"


def test_unknown_keys_in_dotenv_file_are_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The shared .env also holds the generator's settings (ANTHROPIC_*) and those of
    # later epics; they must not break the inbox's startup
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=sk-ant-not-used-here\nAPP_TIMEZONE=America/Toronto\nWEATHER_CITY=Toronto\n"
    )
    monkeypatch.setattr(config, "ENV_FILE", env_file)

    settings = get_settings()

    assert settings.app_env == "development"
    assert not hasattr(settings, "anthropic_api_key")  # the inbox has no AI setting


def test_env_file_is_the_repo_root_dotenv_regardless_of_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.undo()  # restore the real ENV_FILE patched by the autouse fixture

    assert config.ENV_FILE == REPO_ROOT / ".env"


def test_repr_does_not_reveal_the_ingest_token() -> None:
    settings = Settings(ingest_token="super-secret-value", _env_file=None)

    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings)


def test_get_settings_is_cached_until_cleared() -> None:
    first = get_settings()

    assert get_settings() is first

    get_settings.cache_clear()
    assert get_settings() is not first


def test_ingest_token_is_optional_and_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    assert get_settings().ingest_token is None

    monkeypatch.setenv("INGEST_TOKEN", "s3cret-token")
    get_settings.cache_clear()
    settings = get_settings()

    assert settings.ingest_token is not None
    assert settings.ingest_token.get_secret_value() == "s3cret-token"
    assert "s3cret-token" not in repr(settings)  # SecretStr hides it


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_ingest_token_means_ingest_disabled(
    monkeypatch: pytest.MonkeyPatch, blank: str
) -> None:
    # A .env copied from .env.example contains `INGEST_TOKEN=` (empty)
    monkeypatch.setenv("INGEST_TOKEN", blank)

    assert get_settings().ingest_token is None
