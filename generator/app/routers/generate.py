"""POST /api/generate: generate emails with Claude, then deliver them to the inbox."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.schemas import GenerateRequest, GenerateResult
from app.services.ai_client import AIClient, get_ai_client
from app.services.generator import generate_emails
from app.services.inbox import InboxClient, InboxError, get_inbox_client

logger = logging.getLogger(__name__)
router = APIRouter(tags=["generate"])

# Both dependencies run before the endpoint: a missing API key or INGEST_TOKEN
# answers 503 before any (paid) Claude call is made
AIDep = Annotated[AIClient, Depends(get_ai_client)]
InboxDep = Annotated[InboxClient, Depends(get_inbox_client)]


# A plain `def` (not `async def`): the Claude and inbox calls block, so FastAPI
# runs this in a worker thread and other requests keep being served.
@router.post(
    "/generate",
    response_model=GenerateResult,
    status_code=status.HTTP_201_CREATED,
    summary="Generate sample emails with Claude and deliver them to the inbox",
    responses={
        502: {"description": "Claude failed, or the inbox could not be reached / refused"},
        503: {"description": "Not configured: ANTHROPIC_API_KEY or INGEST_TOKEN missing"},
    },
)
def generate(request: GenerateRequest, ai: AIDep, inbox: InboxDep) -> GenerateResult:
    # 1. Claude first: if it fails, nothing is sent to the inbox
    emails = generate_emails(ai, count=request.count, scenario=request.scenario)

    # 2. Deliver all of them in one request (the inbox saves all or nothing)
    try:
        delivered = inbox.deliver(emails)
    except InboxError as exc:
        # The emails are not kept: say clearly that this run delivered nothing
        raise InboxError(
            f"Generated {len(emails)} emails but {exc} Nothing was delivered."
        ) from exc
    return GenerateResult(generated=len(emails), delivered=delivered)
