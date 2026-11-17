"""Email endpoints: /api/emails/..."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.db import get_session
from app.models import Email
from app.schemas import EmailRead, GenerateRequest
from app.services.ai_client import AIClient, get_ai_client
from app.services.generator import generate_emails

router = APIRouter(prefix="/emails", tags=["emails"])

SessionDep = Annotated[Session, Depends(get_session)]
AIDep = Annotated[AIClient, Depends(get_ai_client)]


# A plain `def` (not `async def`): the Claude call blocks for several seconds,
# so FastAPI runs this in a worker thread and other requests keep being served.
@router.post(
    "/generate",
    response_model=list[EmailRead],
    status_code=status.HTTP_201_CREATED,
    summary="Generate sample emails with Claude and save them",
    responses={
        502: {"description": "The AI call failed or produced no valid emails"},
        503: {"description": "AI is not configured (API key missing or rejected)"},
    },
)
def generate(request: GenerateRequest, session: SessionDep, ai: AIDep) -> list[Email]:
    # 1. Talk to Claude first: if it fails, the database is never touched
    generated = generate_emails(ai, count=request.count, scenario=request.scenario)

    # 2. Save all emails in one transaction (all or nothing)
    emails = [Email(**item.model_dump()) for item in generated]
    session.add_all(emails)
    session.commit()
    for email in emails:
        session.refresh(email)  # load the database-assigned id and defaults
    return emails
