"""Email endpoints: /api/emails/..."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, col, func, select

from app.db import get_session
from app.models import ClassificationSource, Email, EmailStatus, Priority
from app.priorities import default_minutes
from app.schemas import (
    Classification,
    ClassifyResult,
    EmailRead,
    EmailUpdate,
    GenerateRequest,
    SourceCounts,
)
from app.services.ai_client import AIClient, get_ai_client, get_optional_ai_client
from app.services.classifier import classify_emails
from app.services.generator import generate_emails

router = APIRouter(prefix="/emails", tags=["emails"])

SessionDep = Annotated[Session, Depends(get_session)]
AIDep = Annotated[AIClient, Depends(get_ai_client)]
# Classification has a fallback, so a missing key means "use the rules", not 503
OptionalAIDep = Annotated[AIClient | None, Depends(get_optional_ai_client)]

# At most this many emails per classify request (3 AI batches, ~20 s): keeps
# every request far below nginx's 180 s timeout. The client calls again while
# `remaining` > 0.
CLASSIFY_LIMIT = 50


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


def _apply(email: Email, classification: Classification) -> None:
    email.priority = classification.priority
    email.priority_reason = classification.reason
    email.suggested_response_minutes = classification.suggested_response_minutes
    email.classification_source = classification.source


def _unclassified_count(session: Session) -> int:
    query = select(func.count()).select_from(Email).where(col(Email.priority).is_(None))
    return session.exec(query).one()


@router.post(
    "/classify",
    response_model=ClassifyResult,
    summary="Classify unclassified emails (newest first, up to 50 per request)",
)
def classify_unclassified(session: SessionDep, ai: OptionalAIDep) -> ClassifyResult:
    # Only emails without a priority: AI, fallback and manual results are never
    # overwritten. Two simultaneous calls could classify the same emails twice;
    # harmless (last save wins) for a single-user app.
    query = (
        select(Email)
        .where(col(Email.priority).is_(None))
        .order_by(col(Email.received_at).desc(), col(Email.id).desc())
        .limit(CLASSIFY_LIMIT)
    )
    emails = list(session.exec(query))
    results = classify_emails(emails, ai) if emails else {}

    for email in emails:
        _apply(email, results[email.id])  # type: ignore[index]
    session.add_all(emails)
    session.commit()  # one transaction for the whole request
    for email in emails:
        session.refresh(email)

    sources = [c.source for c in results.values()]
    return ClassifyResult(
        classified=len(emails),
        by_source=SourceCounts(
            ai=sources.count(ClassificationSource.AI),
            fallback=sources.count(ClassificationSource.FALLBACK),
        ),
        remaining=_unclassified_count(session),
        emails=[EmailRead.model_validate(email) for email in emails],
    )


@router.post(
    "/{email_id}/classify",
    response_model=EmailRead,
    summary="Classify (or re-classify) one email",
    responses={404: {"description": "Email not found"}},
)
def classify_one(email_id: int, session: SessionDep, ai: OptionalAIDep) -> Email:
    # Explicit request for one email: re-classify even if it already has a
    # priority (including a manual one)
    email = session.get(Email, email_id)
    if email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    _apply(email, classify_emails([email], ai)[email_id])
    session.add(email)
    session.commit()
    session.refresh(email)
    return email


MANUAL_REASON = "Set manually."


@router.patch(
    "/{email_id}",
    response_model=EmailRead,
    summary="Change an email's priority (manual override) and/or status",
    responses={404: {"description": "Email not found"}},
)
def update_email(email_id: int, update: EmailUpdate, session: SessionDep) -> Email:
    # PATCH = partial update: only the fields that were sent are changed
    email = session.get(Email, email_id)
    if email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")

    if update.priority is not None:
        # The person's decision wins: marked manual, so bulk classify never touches it
        email.priority = update.priority
        email.priority_reason = MANUAL_REASON
        email.classification_source = ClassificationSource.MANUAL
        email.suggested_response_minutes = default_minutes(update.priority)
    if update.status is not None:
        email.status = update.status

    session.add(email)
    session.commit()
    session.refresh(email)
    return email
