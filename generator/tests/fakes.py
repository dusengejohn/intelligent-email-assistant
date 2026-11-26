"""Test doubles shared by several test files.

`FakeAI` stands in for `AIClient` (same `parse(...)` method, no network): it
returns prepared results in order, raising them if they are exceptions, and
records every call. `FakeInbox` plays the inbox for httpx (`MockTransport`).
"""

import json
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel

from app.schemas import GeneratedBatch, RawEmail


def raw(n: int, **overrides: Any) -> RawEmail:
    """One valid AI email; override fields to make it invalid."""
    values: dict[str, Any] = {
        "sender_name": f"Sender {n}",
        "sender_email": f"sender{n}@example.com",
        "subject": f"Subject {n}",
        "body": f"Body of email {n}. SECRET-BODY-TEXT",
        "received_minutes_ago": n * 60,
    }
    values.update(overrides)
    return RawEmail(**values)


def batch(size: int, start: int = 0) -> GeneratedBatch:
    """A batch of `size` valid AI emails."""
    return GeneratedBatch(emails=[raw(start + i) for i in range(size)])


class FakeAI:
    def __init__(self, *results: BaseModel | Exception) -> None:
        self._results = list(results)
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        result = self._results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeInbox:
    """A pretend inbox: records each request and answers with `respond(request)`.

    By default it accepts everything like the real inbox (201 with ids).
    """

    def __init__(self, respond: Callable[[httpx.Request], httpx.Response] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self._respond = respond or self.accept

    @staticmethod
    def accept(request: httpx.Request) -> httpx.Response:
        count = len(json.loads(request.content)["emails"])
        return httpx.Response(201, json={"created": count, "ids": list(range(1, count + 1))})

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._respond(request)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def delivered(self, call: int = -1) -> list[dict[str, Any]]:
        return json.loads(self.requests[call].content)["emails"]
