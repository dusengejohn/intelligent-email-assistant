"""The only place in the generator that talks to the Claude API (brief §9).

Started as a copy of the inbox's client (story 3b.2, so each service could upgrade
the SDK on its own). Since #92 the inbox has no AI client, so this is the project's
only Claude caller.

Everything else calls `AIClient.parse(...)` and gets back a validated Pydantic
object, or one of two errors: `AIConfigError` / `AIServiceError`.
"""

import logging
import time
from typing import Annotated, Any

import anthropic
from fastapi import Depends
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings
from app.services.errors import AIConfigError, AIServiceError

logger = logging.getLogger(__name__)

# The tasks here are simple (write / label short emails): low effort is enough,
# and it is faster and uses fewer output tokens than the default (medium).
EFFORT = "low"
MAX_RETRIES = 1


class AIClient:
    """Small adapter around the Anthropic SDK.

    `sdk_client` can be passed in (dependency injection), so tests use a fake
    instead of the real SDK and never touch the network.
    """

    def __init__(self, settings: Settings, sdk_client: Any | None = None) -> None:
        self.model = settings.anthropic_model
        if sdk_client is None:
            if settings.anthropic_api_key is None:
                raise AIConfigError("AI is not configured: set ANTHROPIC_API_KEY in .env")
            sdk_client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key.get_secret_value(),
                timeout=settings.ai_timeout_seconds,
                max_retries=MAX_RETRIES,
            )
        self.sdk = sdk_client

    def parse[T: BaseModel](
        self, *, system: str, prompt: str, output_model: type[T], max_tokens: int = 16000
    ) -> T:
        """Ask Claude for JSON matching `output_model` and return it validated."""
        started = time.perf_counter()
        try:
            response = self.sdk.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=output_model,
                output_config={"effort": EFFORT},
            )
        # Most specific first: e.g. APITimeoutError is a kind of APIConnectionError,
        # and every HTTP error is a kind of APIStatusError. `from exc` keeps the
        # original error attached for debugging; users only see our short message.
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise self._fail(
                AIConfigError, "AI is not configured: ANTHROPIC_API_KEY was rejected", exc
            ) from exc
        except anthropic.RateLimitError as exc:
            raise self._fail(AIServiceError, "busy (rate limited); try again.", exc) from exc
        except anthropic.APITimeoutError as exc:
            raise self._fail(AIServiceError, "request timed out; try again.", exc) from exc
        except anthropic.APIConnectionError as exc:
            raise self._fail(AIServiceError, "could not reach the AI service.", exc) from exc
        except anthropic.APIStatusError as exc:
            raise self._fail(
                AIServiceError, f"unexpected response (HTTP {exc.status_code}).", exc
            ) from exc
        except ValidationError as exc:
            # The SDK validates inside parse(): cut-off or non-JSON output lands here
            raise self._fail(AIServiceError, "returned invalid output.", exc) from exc

        duration_ms = (time.perf_counter() - started) * 1000
        usage = response.usage
        logger.info(
            "Claude call: model=%s output=%s duration_ms=%.0f input_tokens=%s "
            "output_tokens=%s stop_reason=%s",
            self.model,
            output_model.__name__,
            duration_ms,
            usage.input_tokens,
            usage.output_tokens,
            response.stop_reason,
        )

        # Only trust output from a normal finish
        if response.stop_reason == "refusal":
            raise AIServiceError("declined the request (refusal).")
        if response.stop_reason == "max_tokens":
            raise AIServiceError("output was cut off (max tokens reached).")
        if response.parsed_output is None:
            raise AIServiceError("returned no structured output.")
        return response.parsed_output

    def _fail[E: Exception](self, error_type: type[E], message: str, cause: Exception) -> E:
        # Log only the exception type: SDK messages can include response bodies
        logger.warning("Claude call failed: model=%s error=%s", self.model, type(cause).__name__)
        return error_type(message)


def get_ai_client(settings: Annotated[Settings, Depends(get_settings)]) -> AIClient:
    """FastAPI dependency. Raises AIConfigError when no API key is configured."""
    return AIClient(settings)
