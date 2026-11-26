"""Errors raised by the AI layer (see ai_client.py).

Their messages are short and safe to show to a user: no API key, no stack
trace, no raw response body. Routers map them to HTTP status codes.
"""


class AIError(Exception):
    """Base class for every AI-related failure."""


class AIConfigError(AIError):
    """Claude is not usable as configured: the API key is missing or rejected."""


class AIServiceError(AIError):
    """Claude was reachable in principle but this call failed (timeout, rate
    limit, server error, refusal, truncated or invalid output)."""
