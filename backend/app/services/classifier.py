"""Classify emails with Claude, falling back to the rules for anything that fails.

Every email always gets exactly one valid Classification. Fallback policy:

  | Situation                                           | Emails affected       |
  |-----------------------------------------------------|-----------------------|
  | ai is None (no API key)                             | all -> rules          |
  | AIConfigError (key rejected)                        | this + later batches  |
  |                                                     | -> rules, no more calls|
  | AIServiceError (timeout, rate limit, refusal, ...)  | this batch -> rules   |
  | invalid / duplicate / unknown-id item, missing email| those emails -> rules |
  | valid item                                          | that email -> AI      |

Never raises because of the AI (graceful degradation, brief §10).
"""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import ValidationError

from app.models import ClassificationSource, Email
from app.schemas import Classification, ClassificationBatch
from app.services.ai_client import AIClient
from app.services.errors import AIConfigError, AIServiceError
from app.services.fallback import classify_fallback
from app.services.prompts import CLASSIFY_EMAILS_SYSTEM, build_classify_prompt

logger = logging.getLogger(__name__)

# Classification output is short (~45 tokens per email), so batches can be larger
# than for generation; input dominates (~135 tokens per email).
BATCH_SIZE = 20
MAX_BODY_CHARS = 2000  # cost guard for long emails
MAX_TOKENS = 4000  # ~20 results x ~45 tokens, with plenty of room


def classify_emails(emails: Sequence[Email], ai: AIClient | None) -> dict[int, Classification]:
    """Return {email id: Classification} for every email, preferring the AI."""
    if any(email.id is None for email in emails):
        raise ValueError("emails must be saved (have an id) before classifying")

    results: dict[int, Classification] = {}
    rejected = 0  # AI items that failed validation (counted, never logged in full)
    use_ai = ai is not None
    now = datetime.now(UTC)

    for start in range(0, len(emails), BATCH_SIZE):
        batch = emails[start : start + BATCH_SIZE]
        if ai is not None and use_ai:
            try:
                answer = ai.parse(
                    system=CLASSIFY_EMAILS_SYSTEM,
                    prompt=build_classify_prompt(batch, now, MAX_BODY_CHARS),
                    output_model=ClassificationBatch,
                    max_tokens=MAX_TOKENS,
                )
                accepted, skipped = _valid_results(answer, {e.id for e in batch if e.id})
                results.update(accepted)
                rejected += skipped
            except AIConfigError:
                # A rejected key won't fix itself: stop calling the AI for this run
                logger.warning("AI key rejected: classifying the remaining emails with rules")
                use_ai = False
            except AIServiceError as exc:
                logger.warning("AI batch failed (%s): using rules for this batch", exc)

        for email in batch:
            if email.id not in results:  # no AI, failed batch, invalid or missing item
                results[email.id] = classify_fallback(email)  # type: ignore[index]

    by_source = {source: 0 for source in (ClassificationSource.AI, ClassificationSource.FALLBACK)}
    for classification in results.values():
        by_source[classification.source] += 1
    logger.info(
        "Classified %d emails: ai=%d fallback=%d (AI items rejected: %d)",
        len(results),
        by_source[ClassificationSource.AI],
        by_source[ClassificationSource.FALLBACK],
        rejected,
    )
    return results


def _valid_results(
    answer: ClassificationBatch, batch_ids: set[int]
) -> tuple[dict[int, Classification], int]:
    """Strict per-item check. Returns (accepted by id, number of items skipped)."""
    accepted: dict[int, Classification] = {}
    skipped = 0
    for item in answer.results:
        if item.email_id not in batch_ids or item.email_id in accepted:
            skipped += 1  # invented id, or a later duplicate (first valid one wins)
            continue
        try:
            accepted[item.email_id] = Classification(
                priority=item.priority,  # type: ignore[arg-type]  (validated to a Priority)
                reason=item.reason.strip(),
                suggested_response_minutes=item.suggested_response_minutes,
                source=ClassificationSource.AI,
            )
        except ValidationError:
            skipped += 1
    return accepted, skipped
