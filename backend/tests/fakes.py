"""Test doubles shared by several test files.

`FakeAI` stands in for `AIClient`: same `parse(...)` method, no network. It
returns prepared results in order (raising them if they are exceptions) and
records every call, so tests can assert on the prompts that were sent.
"""

from typing import Any

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
