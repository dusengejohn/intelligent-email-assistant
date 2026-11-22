"""Request/response and AI data shapes (not database tables: see models.py).

Generated emails pass two layers of validation:
1. `GeneratedBatch` / `RawEmail`: the *shape* Claude must return. Deliberately
   lenient (plain str/int), so one bad email can't fail the whole AI call.
2. `GeneratedEmail`: our *business rules*, checked per email. Emails that fail
   are skipped, so only well-formed emails can reach the database.
"""

from datetime import UTC, datetime, timedelta
from typing import Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

from app.models import ClassificationSource, EmailStatus, Priority

# Domains reserved for documentation (RFC 2606): guaranteed never to be real
# mailboxes. Generated senders must use one of these (or a subdomain).
FICTIONAL_DOMAINS = ("example.com", "example.org", "example.net")
MAX_AGE = timedelta(hours=48)
# Tolerance for the few milliseconds between computing and checking a timestamp
CLOCK_GRACE = timedelta(seconds=1)


class RawEmail(BaseModel):
    """One email exactly as Claude returns it (shape only, no rules)."""

    sender_name: str
    sender_email: str
    subject: str
    body: str
    received_minutes_ago: int


class GeneratedBatch(BaseModel):
    """The JSON object Claude must return: `{"emails": [...]}`."""

    emails: list[RawEmail]


class GeneratedEmail(BaseModel):
    """A generated email that passed every business rule."""

    model_config = ConfigDict(str_strip_whitespace=True)

    sender_name: str = Field(min_length=1, max_length=100)
    sender_email: EmailStr
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=2000)
    received_at: AwareDatetime

    @field_validator("sender_email")
    @classmethod
    def must_be_fictional(cls, value: str) -> str:
        domain = value.rsplit("@", 1)[1].lower()
        if not any(domain == d or domain.endswith("." + d) for d in FICTIONAL_DOMAINS):
            raise ValueError(f"domain must be one of {', '.join(FICTIONAL_DOMAINS)}")
        return value

    @field_validator("received_at")
    @classmethod
    def must_be_within_last_48_hours(cls, value: datetime) -> datetime:
        value = value.astimezone(UTC)
        age = datetime.now(UTC) - value
        if age < -CLOCK_GRACE:
            raise ValueError("received_at is in the future")
        if age > MAX_AGE + CLOCK_GRACE:
            raise ValueError("received_at is older than 48 hours")
        return value

    @classmethod
    def from_raw(cls, raw: RawEmail, now: datetime) -> Self:
        """Apply the rules to one AI item. Raises ValidationError if it breaks any.

        Claude doesn't know the current time, so it says "N minutes ago" and
        Python computes the exact timestamp.
        """
        return cls.model_validate(
            {
                "sender_name": raw.sender_name,
                "sender_email": raw.sender_email,
                "subject": raw.subject,
                "body": raw.body,
                "received_at": now - timedelta(minutes=raw.received_minutes_ago),
            }
        )


# --- API request / response models ------------------------------------------


class GenerateRequest(BaseModel):
    """Body of POST /api/emails/generate."""

    count: int = Field(default=10, ge=1, le=50, description="How many emails to generate")
    scenario: str | None = Field(
        default=None,
        max_length=200,
        description="Optional context, e.g. 'IT infrastructure team'",
    )


class EmailRead(BaseModel):
    """An email as returned by the API (all fields; timestamps are UTC-aware)."""

    model_config = ConfigDict(from_attributes=True)  # build directly from an Email row

    id: int
    sender_name: str
    sender_email: str
    subject: str
    body: str
    received_at: datetime
    priority: Priority | None
    priority_reason: str | None
    classification_source: ClassificationSource | None
    suggested_response_minutes: int | None
    status: EmailStatus
    created_at: datetime


# --- Classification ------------------------------------------------------------


class Classification(BaseModel):
    """One email's priority, from the AI, the fallback rules or a person."""

    priority: Priority
    reason: str = Field(min_length=1, max_length=200, description="One sentence")
    suggested_response_minutes: int = Field(ge=1, le=480)
    source: ClassificationSource


class RawClassification(BaseModel):
    """One AI classification exactly as Claude returns it (shape only, no rules)."""

    email_id: int
    priority: str
    reason: str
    suggested_response_minutes: int


class ClassificationBatch(BaseModel):
    """The JSON object Claude must return when classifying: `{"results": [...]}`."""

    results: list[RawClassification]


class SourceCounts(BaseModel):
    ai: int
    fallback: int


class ClassifyResult(BaseModel):
    """Response of POST /api/emails/classify."""

    classified: int = Field(description="Emails classified by this request")
    by_source: SourceCounts
    remaining: int = Field(description="Unclassified emails left; call again if > 0")
    emails: list[EmailRead] = Field(description="The emails classified by this request")


class EmailUpdate(BaseModel):
    """Body of PATCH /api/emails/{id}: send only the fields you want to change."""

    # Unknown fields ("subject", typos like "priorty") are an error, not silently ignored
    model_config = ConfigDict(extra="forbid")

    priority: Priority | None = Field(default=None, description="Manual priority override")
    status: EmailStatus | None = Field(default=None, description="new or handled")

    @model_validator(mode="after")
    def at_least_one_field_and_no_nulls(self) -> Self:
        # model_fields_set = the fields that were actually in the request. It tells
        # "not sent" (leave unchanged) apart from "sent as null" (not allowed).
        if not self.model_fields_set:
            raise ValueError("send at least one of: priority, status")
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self
