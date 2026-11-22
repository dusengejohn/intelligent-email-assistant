"""Test doubles shared by several test files.

`FakeAI` stands in for `AIClient`: same `parse(...)` method, no network. It
returns prepared results in order (raising them if they are exceptions) and
records every call, so tests can assert on the prompts that were sent.
"""

import re
from typing import Any

from pydantic import BaseModel

from app.schemas import ClassificationBatch, GeneratedBatch, RawClassification, RawEmail


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


class EchoClassifierAI:
    """Fake AI for classification: answers every `<email id="N">` in the prompt.

    Ids only exist after rows are saved, so the answer is built from the prompt
    instead of being prepared in advance. Set `error` to make every call fail.
    """

    def __init__(self, priority: str = "high", error: Exception | None = None) -> None:
        self.priority = priority
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def sent_ids(self, call: int = -1) -> list[int]:
        return [int(i) for i in re.findall(r'<email id="(\d+)">', self.calls[call]["prompt"])]

    def parse(self, **kwargs: Any) -> ClassificationBatch:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return ClassificationBatch(
            results=[
                RawClassification(
                    email_id=email_id,
                    priority=self.priority,
                    reason="Classified by the fake AI.",
                    suggested_response_minutes=20,
                )
                for email_id in self.sent_ids()
            ]
        )
