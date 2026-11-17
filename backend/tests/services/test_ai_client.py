"""Tests for the Claude API wrapper (story 1.3, issue #29).

No test talks to the network: the real SDK is replaced by `FakeSDK`, a small
stand-in with the same `messages.parse(...)` method that records every call.
"""

import logging
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.services.ai_client import AIClient, get_ai_client
from app.services.errors import AIConfigError, AIServiceError

API_KEY = "sk-ant-test-key-never-logged"
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


class Answer(BaseModel):
    city: str
    population: int


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {"anthropic_api_key": API_KEY, "_env_file": None}
    values.update(overrides)
    return Settings(**values)


TORONTO = Answer(city="Toronto", population=3_000_000)


def make_response(
    parsed: BaseModel | None = TORONTO,
    stop_reason: str = "end_turn",
) -> SimpleNamespace:
    """Looks like the SDK's ParsedMessage for the fields AIClient reads."""
    return SimpleNamespace(
        parsed_output=parsed,
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=120, output_tokens=45),
    )


class FakeSDK:
    """Stand-in for `anthropic.Anthropic`: returns `response` or raises `error`."""

    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._response = response if response is not None else make_response()
        self._error = error
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


def make_client(sdk: FakeSDK, **settings: Any) -> AIClient:
    return AIClient(make_settings(**settings), sdk_client=sdk)


def ask(client: AIClient) -> Answer:
    return client.parse(system="You answer in JSON.", prompt="Biggest city?", output_model=Answer)


def status_error(cls: type[anthropic.APIStatusError], status: int) -> anthropic.APIStatusError:
    return cls("boom", response=httpx2.Response(status, request=REQUEST), body=None)


def pydantic_error() -> ValidationError:
    try:
        Answer.model_validate_json('{"city": "Toron')  # truncated JSON
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")


# --- get_ai_client() -------------------------------------------------------


def test_get_ai_client_without_key_raises_config_error() -> None:
    with pytest.raises(AIConfigError):
        get_ai_client(make_settings(anthropic_api_key=None))


def test_get_ai_client_builds_sdk_with_settings() -> None:
    # Creating the SDK object makes no network call; only requests do.
    client = get_ai_client(make_settings(ai_timeout_seconds=12))

    sdk = client.sdk
    assert isinstance(sdk, anthropic.Anthropic)
    assert sdk.api_key == API_KEY
    assert sdk.timeout == 12
    assert sdk.max_retries == 1


# --- parse(): success ------------------------------------------------------


def test_parse_returns_validated_model() -> None:
    answer = ask(make_client(FakeSDK()))

    assert answer == TORONTO


def test_request_uses_settings_and_no_sampling_parameters() -> None:
    sdk = FakeSDK()

    make_client(sdk, anthropic_model="claude-test-model").parse(
        system="sys", prompt="hello", output_model=Answer, max_tokens=500
    )

    (call,) = sdk.calls
    assert call["model"] == "claude-test-model"
    assert call["system"] == "sys"
    assert call["messages"] == [{"role": "user", "content": "hello"}]
    assert call["max_tokens"] == 500
    assert call["output_format"] is Answer
    assert call["output_config"] == {"effort": "low"}
    for sampling in ("temperature", "top_p", "top_k"):
        assert sampling not in call


# --- parse(): error mapping ------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        status_error(anthropic.AuthenticationError, 401),
        status_error(anthropic.PermissionDeniedError, 403),
    ],
    ids=["401", "403"],
)
def test_rejected_key_raises_config_error(error: Exception) -> None:
    with pytest.raises(AIConfigError):
        ask(make_client(FakeSDK(error=error)))


@pytest.mark.parametrize(
    ("error", "expected_text"),
    [
        (status_error(anthropic.RateLimitError, 429), "busy"),
        (anthropic.APITimeoutError(request=REQUEST), "timed out"),
        (anthropic.APIConnectionError(request=REQUEST), "could not reach"),
        (status_error(anthropic.InternalServerError, 500), "HTTP 500"),
        (pydantic_error(), "invalid"),
    ],
    ids=["rate-limit", "timeout", "connection", "server-500", "invalid-output"],
)
def test_service_failures_raise_service_error(error: Exception, expected_text: str) -> None:
    with pytest.raises(AIServiceError) as exc_info:
        ask(make_client(FakeSDK(error=error)))

    message = str(exc_info.value)
    assert expected_text in message.lower() or expected_text in message
    assert API_KEY not in message
    assert len(message) < 120  # short and safe: no stack dump, no response body


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_untrustworthy_stop_reason_raises_service_error(stop_reason: str) -> None:
    sdk = FakeSDK(response=make_response(stop_reason=stop_reason))

    with pytest.raises(AIServiceError, match=stop_reason.replace("_", " ")):
        ask(make_client(sdk))


def test_missing_parsed_output_raises_service_error() -> None:
    sdk = FakeSDK(response=make_response(parsed=None))

    with pytest.raises(AIServiceError):
        ask(make_client(sdk))


# --- logging ---------------------------------------------------------------


def test_successful_call_logs_model_and_token_usage(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.services.ai_client")

    ask(make_client(FakeSDK()))

    assert "claude-haiku-5-5" in caplog.text
    assert "input_tokens=120" in caplog.text
    assert "output_tokens=45" in caplog.text


def test_api_key_is_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)

    ask(make_client(FakeSDK()))
    with pytest.raises(AIConfigError):
        ask(make_client(FakeSDK(error=status_error(anthropic.AuthenticationError, 401))))

    assert API_KEY not in caplog.text
