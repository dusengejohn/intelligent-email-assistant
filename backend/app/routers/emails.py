"""Email endpoints: /api/emails/..."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, col, select

from app.db import get_session
from app.models import Email, EmailStatus, Priority
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


@router.get("", response_model=list[EmailRead], summary="List emails, newest first")
def list_emails(
    session: SessionDep,
    # `alias`: the URL still says ?status=..., but the Python name doesn't hide
    # FastAPI's `status` module imported above
    email_status: Annotated[EmailStatus | None, Query(alias="status")] = None,
    priority: Priority | None = None,
) -> list[Email]:
    # Typed as enums: FastAPI rejects unknown values with 422 and lists the
    # allowed ones in /docs. Filters are added only when given.
    query = select(Email)
    if email_status is not None:
        query = query.where(Email.status == email_status)
    if priority is not None:
        query = query.where(Email.priority == priority)
    # id breaks ties, so emails with the same received_at never swap places
    query = query.order_by(col(Email.received_at).desc(), col(Email.id).desc())
    return list(session.exec(query))


@router.get(
    "/{email_id}",
    response_model=EmailRead,
    summary="Get one email",
    responses={404: {"description": "Email not found"}},
)
def get_email(email_id: int, session: SessionDep) -> Email:
    email = session.get(Email, email_id)
    if email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    return email
