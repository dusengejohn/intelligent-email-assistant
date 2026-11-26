"""Request/response and AI data shapes.

Generated emails pass two layers of validation (as in the inbox, story 1.4):
1. `GeneratedBatch` / `RawEmail`: the *shape* Claude must return, deliberately
   lenient, so one bad email can't fail the whole AI call.
2. `GeneratedEmail`: the *business rules*, checked per email; failures are skipped.

The inbox validates every delivered email again with the same rules, except
that the generator is one hour stricter about age (47 h instead of 48 h): an
email must still be young enough when it reaches the inbox, up to ~80 s later.
"""

from datetime import UTC, datetime, timedelta
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, field_validator

# Domains reserved for documentation (RFC 2606): never real mailboxes
FICTIONAL_DOMAINS = ("example.com", "example.org", "example.net")
# The inbox accepts 48 h; one hour of margin for the time until delivery
MAX_AGE = timedelta(hours=47)
MAX_MINUTES_AGO = int(MAX_AGE.total_seconds() // 60)  # 2820
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
    """A generated email that passed every rule: exactly what is delivered."""

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
    def must_be_within_max_age(cls, value: datetime) -> datetime:
        value = value.astimezone(UTC)
        age = datetime.now(UTC) - value
        if age < -CLOCK_GRACE:
            raise ValueError("received_at is in the future")
        if age > MAX_AGE + CLOCK_GRACE:
            raise ValueError("received_at is older than 47 hours")
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


# --- API request / response ------------------------------------------------------


class GenerateRequest(BaseModel):
    """Body of POST /api/generate."""

    count: int = Field(default=10, ge=1, le=50, description="How many emails to generate")
    scenario: str | None = Field(
        default=None,
        max_length=200,
        description="Optional context, e.g. 'IT infrastructure team'",
    )


class GenerateResult(BaseModel):
    """Response of POST /api/generate."""

    generated: int = Field(description="Valid emails Claude produced")
    delivered: int = Field(description="Emails the inbox accepted")
