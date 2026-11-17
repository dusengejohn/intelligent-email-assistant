"""Tests for app.config (story 1.1, issue #27)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app import config
from app.config import Settings, get_settings

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_api_key_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "abc")

    key = get_settings().anthropic_api_key

    assert key is not None
    assert key.get_secret_value() == "abc"


def test_api_key_is_none_when_not_set() -> None:
    assert get_settings().anthropic_api_key is None


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_api_key_is_treated_as_not_configured(
    monkeypatch: pytest.MonkeyPatch, blank: str
) -> None:
    # A .env copied from .env.example contains `ANTHROPIC_API_KEY=` (empty)
    monkeypatch.setenv("ANTHROPIC_API_KEY", blank)

    assert get_settings().anthropic_api_key is None


def test_values_are_read_from_dotenv_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=from-file\nANTHROPIC_MODEL=model-from-file\n")
    monkeypatch.setattr(config, "ENV_FILE", env_file)

    settings = get_settings()

    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "from-file"
    assert settings.anthropic_model == "model-from-file"


def test_environment_variable_overrides_dotenv_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_MODEL=model-from-file\n")
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    monkeypatch.setenv("ANTHROPIC_MODEL", "model-from-env")

    assert get_settings().anthropic_model == "model-from-env"


def test_unknown_keys_in_dotenv_file_are_ignored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # .env also holds settings for later epics; they must not break startup
    env_file = tmp_path / ".env"
    env_file.write_text("APP_TIMEZONE=America/Toronto\nWEATHER_CITY=Toronto\n")
    monkeypatch.setattr(config, "ENV_FILE", env_file)

    assert get_settings().app_env == "development"


def test_env_file_is_the_repo_root_dotenv_regardless_of_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.undo()  # restore the real ENV_FILE patched by the autouse fixture

    assert config.ENV_FILE == REPO_ROOT / ".env"


def test_repr_does_not_reveal_api_key() -> None:
    settings = Settings(anthropic_api_key="super-secret-value", _env_file=None)

    assert "super-secret-value" not in repr(settings)
    assert "super-secret-value" not in str(settings)


def test_model_defaults_to_haiku() -> None:
    assert get_settings().anthropic_model == "claude-haiku-5-5"


def test_model_can_be_overridden_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

    assert get_settings().anthropic_model == "claude-sonnet-5-5"


def test_ai_timeout_defaults_to_30_seconds() -> None:
    assert get_settings().ai_timeout_seconds == 30


@pytest.mark.parametrize("bad_value", ["0", "-5", "abc"])
def test_invalid_ai_timeout_is_rejected(monkeypatch: pytest.MonkeyPatch, bad_value: str) -> None:
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", bad_value)

    with pytest.raises(ValidationError):
        get_settings()


def test_get_settings_is_cached_until_cleared() -> None:
    first = get_settings()

    assert get_settings() is first

    get_settings.cache_clear()
    assert get_settings() is not first
