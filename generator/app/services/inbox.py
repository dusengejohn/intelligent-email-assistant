"""Delivers generated emails to the inbox: `POST {INBOX_URL}/api/emails/ingest`.

The only place in the generator that talks to the inbox. Every failure becomes
an `InboxError` with a short message that is safe to show (never the token).
"""

import logging
from typing import Annotated

import httpx
from fastapi import Depends

from app.config import Settings, get_settings
from app.schemas import GeneratedEmail

logger = logging.getLogger(__name__)

INGEST_PATH = "/api/emails/ingest"


class InboxConfigError(Exception):
    """Delivery is not set up on our side (no INGEST_TOKEN): HTTP 503."""


class InboxError(Exception):
    """The inbox could not be reached or refused the delivery: HTTP 502."""


class InboxClient:
    """Small adapter around httpx.

    `transport` can be passed in (dependency injection), so tests use a fake
    inbox (`httpx.MockTransport`) instead of the network.
    """

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        if settings.ingest_token is None:
            raise InboxConfigError(
                "Delivery is not configured: set INGEST_TOKEN in .env "
                "(the same value as the inbox's)"
            )
        self.base_url = settings.inbox_url.rstrip("/")
        self.url = self.base_url + INGEST_PATH
        self.timeout = settings.inbox_timeout_seconds
        self._token = settings.ingest_token
        self._transport = transport

    def deliver(self, emails: list[GeneratedEmail]) -> int:
        """Send all emails in one request; return how many the inbox created."""
        # mode="json": datetimes become UTC ISO 8601 strings ("...Z")
        payload = {"emails": [email.model_dump(mode="json") for email in emails]}
        headers = {"X-Ingest-Token": self._token.get_secret_value()}
        try:
            with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
                response = client.post(self.url, json=payload, headers=headers)
        # Most specific first: a timeout is also a kind of transport error
        except httpx.TimeoutException as exc:
            raise self._fail(f"the inbox did not answer within {self.timeout} s.", exc) from exc
        except httpx.TransportError as exc:
            raise self._fail(f"the inbox could not be reached at {self.base_url}.", exc) from exc

        if response.status_code != 201:
            raise self._fail(self._explain(response.status_code))
        try:
            created = int(response.json()["created"])
        except (ValueError, KeyError, TypeError) as exc:
            raise self._fail("the inbox sent an unexpected answer.", exc) from exc
        logger.info("Delivered %d emails to the inbox", created)
        return created

    @staticmethod
    def _explain(status_code: int) -> str:
        if status_code == 401:
            return "the inbox rejected the token (INGEST_TOKEN must be the same in both services)."
        if status_code == 503:
            return "the inbox has ingest disabled (set INGEST_TOKEN for the inbox)."
        if status_code == 422:
            return "the inbox rejected the emails as invalid."
        return f"the inbox answered HTTP {status_code}."

    def _fail(self, message: str, cause: Exception | None = None) -> InboxError:
        # Log the reason and the error type only: never the token or email text
        logger.warning(
            "Delivery to the inbox failed: %s%s",
            message,
            f" ({type(cause).__name__})" if cause else "",
        )
        return InboxError(message)


def get_inbox_client(settings: Annotated[Settings, Depends(get_settings)]) -> InboxClient:
    """FastAPI dependency. Raises InboxConfigError when no INGEST_TOKEN is configured."""
    return InboxClient(settings)
