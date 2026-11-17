"""Generate realistic sample emails with Claude and keep only valid ones."""

import logging
from datetime import UTC, datetime

from pydantic import ValidationError

from app.schemas import GeneratedBatch, GeneratedEmail
from app.services.ai_client import AIClient
from app.services.errors import AIServiceError
from app.services.prompts import GENERATE_EMAILS_SYSTEM, build_generate_prompt

logger = logging.getLogger(__name__)

# Emails per AI call: keeps each response short, fast and far below max_tokens
BATCH_SIZE = 10


def batch_sizes(count: int) -> list[int]:
    """25 -> [10, 10, 5]"""
    full, rest = divmod(count, BATCH_SIZE)
    return [BATCH_SIZE] * full + ([rest] if rest else [])


def generate_emails(ai: AIClient, count: int, scenario: str | None = None) -> list[GeneratedEmail]:
    """Return up to `count` valid emails (fewer if Claude produced invalid ones).

    All-or-nothing: an AIServiceError in any batch propagates, so a caller never
    gets a partial result from a failed run.
    """
    if count < 1:
        raise ValueError("count must be at least 1")

    emails: list[GeneratedEmail] = []
    skipped = 0
    sizes = batch_sizes(count)
    for size in sizes:
        batch = ai.parse(
            system=GENERATE_EMAILS_SYSTEM,
            prompt=build_generate_prompt(size, scenario),
            output_model=GeneratedBatch,
        )
        now = datetime.now(UTC)
        for raw in batch.emails:
            try:
                emails.append(GeneratedEmail.from_raw(raw, now))
            except ValidationError as exc:
                skipped += 1
                # Field names only: error details can contain the email's text
                fields = sorted({str(err["loc"][0]) for err in exc.errors() if err["loc"]})
                logger.debug("Skipped generated email: invalid %s", ", ".join(fields))

    logger.info(
        "Generated %d valid emails (%d skipped) in %d AI calls; requested %d",
        len(emails),
        skipped,
        len(sizes),
        count,
    )
    if not emails:
        raise AIServiceError("AI returned no valid emails; try again.")
    return emails[:count]
