"""Email endpoints: /api/emails/..."""

import logging
import secrets
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import ColumnElement, case, delete
from sqlmodel import Session, col, func, select

from app.config import Settings, get_settings
from app.db import get_session
from app.models import ClassificationSource, Email, EmailStatus, Priority
from app.priorities import default_minutes
from app.schemas import (
    Classification,
    ClassifyResult,
    EmailRead,
    EmailSummary,
    EmailUpdate,
    EmptyTrashResult,
    IngestRequest,
    IngestResult,
    SortOrder,
    SourceCounts,
)
from app.services.ai_client import AIClient, get_optional_ai_client
from app.services.classifier import classify_emails

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/emails", tags=["emails"])

SessionDep = Annotated[Session, Depends(get_session)]
# Classification has a fallback, so a missing key means "use the rules", not 503
OptionalAIDep = Annotated[AIClient | None, Depends(get_optional_ai_client)]

# At most this many emails per classify request (3 AI batches, ~20 s): keeps
# every request far below nginx's 180 s timeout. The client calls again while
# `remaining` > 0.
CLASSIFY_LIMIT = 50


def require_ingest_token(
    settings: Annotated[Settings, Depends(get_settings)],
    token: Annotated[str | None, Header(alias="X-Ingest-Token")] = None,
) -> None:
    """Let a request through only if it carries the shared ingest token.

    FastAPI runs dependencies before it validates the body, so a caller without
    the token gets 401 and learns nothing about our validation rules.
    """
    if settings.ingest_token is None:
        # Fail loudly: a forgotten setting must never mean "accept anything"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ingest is disabled: set INGEST_TOKEN in .env",
        )
    expected = settings.ingest_token.get_secret_value().encode()
    # compare_digest takes the same time however many characters match, so the
    # token can't be guessed character by character from response times
    if token is None or not secrets.compare_digest(token.encode(), expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or wrong X-Ingest-Token header",
        )


@router.post(
    "/ingest",
    response_model=IngestResult,
    status_code=status.HTTP_201_CREATED,
    summary="Receive emails delivered by another service (e.g. the generator)",
    dependencies=[Depends(require_ingest_token)],
    responses={
        401: {"description": "Missing or wrong X-Ingest-Token header"},
        422: {"description": "An email broke a rule: nothing was saved"},
        503: {"description": "Ingest is disabled (INGEST_TOKEN not configured)"},
    },
)
def ingest(request: IngestRequest, session: SessionDep) -> IngestResult:
    # Every email already passed validation (IngestEmail), so save them all in
    # one transaction: either all arrive or none do
    emails = [Email(**item.model_dump()) for item in request.emails]
    session.add_all(emails)
    session.commit()
    ids = [email.id for email in emails if email.id is not None]
    logger.info("Ingested %d emails (ids %s..%s)", len(ids), ids[0], ids[-1])
    return IngestResult(created=len(ids), ids=ids)


def _priority_order() -> list:
    """ORDER BY for the inbox (brief §7), done by the database:

    1. new before handled (handled emails are shown greyed out at the bottom)
    2. unclassified first, then critical -> high -> moderate -> low
    3. newest first, then id (so equal emails never swap places)
    """
    status_rank = case((col(Email.status) == EmailStatus.HANDLED, 1), else_=0)
    priority_rank = case(
        (col(Email.priority).is_(None), 0),
        (col(Email.priority) == Priority.CRITICAL, 1),
        (col(Email.priority) == Priority.HIGH, 2),
        (col(Email.priority) == Priority.MODERATE, 3),
        else_=4,  # low
    )
    return [status_rank, priority_rank, *_newest_order()]


def _newest_order() -> list:
    return [col(Email.received_at).desc(), col(Email.id).desc()]


# --- Soft delete (story 3.3): ONE place for "not in the Trash" -------------------------


def _active() -> ColumnElement[bool]:
    """Filter for emails that are NOT in the Trash. Every query except the Trash
    view and GET /{id} uses it, so a trashed email is invisible everywhere else."""
    return col(Email.deleted_at).is_(None)


def _in_trash() -> ColumnElement[bool]:
    return col(Email.deleted_at).is_not(None)


def _get_or_404(session: Session, email_id: int, *, trashed: bool = False) -> Email:
    """The email with this id, or 404. trashed=False: must be active; True: in the Trash."""
    email = session.get(Email, email_id)
    if email is None or (email.deleted_at is not None) != trashed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    return email


# Declared BEFORE "/{email_id}": FastAPI tries routes in order, and the pattern
# would otherwise read "summary" as an email id (and answer 422).
@router.get("/summary", response_model=EmailSummary, summary="Counts for the inbox views")
def email_summary(session: SessionDep) -> EmailSummary:
    # One query: count emails per (priority, status) group, then add the groups up
    rows = session.exec(
        select(Email.priority, Email.status, func.count())
        .where(_active())
        .group_by(col(Email.priority), col(Email.status))
    ).all()
    counts = dict.fromkeys(EmailSummary.model_fields, 0)
    for priority, email_status, n in rows:
        counts["all"] += n
        counts["classified" if priority else "unclassified"] += n
        if priority:
            counts[priority.value] += n
        if email_status == EmailStatus.HANDLED:
            counts["handled"] += n
    counts["trash"] = session.exec(select(func.count()).select_from(Email).where(_in_trash())).one()
    return EmailSummary(**counts)


@router.get("", response_model=list[EmailRead], summary="List emails (priority order by default)")
def list_emails(
    session: SessionDep,
    # `alias`: the URL still says ?status=..., but the Python name doesn't hide
    # FastAPI's `status` module imported above
    email_status: Annotated[EmailStatus | None, Query(alias="status")] = None,
    priority: Priority | None = None,
    classified: bool | None = None,
    sort: SortOrder = SortOrder.PRIORITY,
    trash: Annotated[bool, Query(description="true: only the Trash, newest deleted first")] = False,
) -> list[Email]:
    # Typed as enums/bools: FastAPI rejects unknown values with 422 and lists the
    # allowed ones in /docs. Filters are added only when given; each sidebar view
    # is one combination of them.
    query = select(Email).where(_in_trash() if trash else _active())
    if email_status is not None:
        query = query.where(Email.status == email_status)
    if priority is not None:
        query = query.where(Email.priority == priority)
    if classified is not None:
        has_priority = col(Email.priority).is_not(None)
        query = query.where(has_priority if classified else col(Email.priority).is_(None))
    if trash:  # like a real Trash: most recently deleted first
        order = [col(Email.deleted_at).desc(), col(Email.id).desc()]
    elif sort == SortOrder.PRIORITY:
        order = _priority_order()
    else:
        order = _newest_order()
    return list(session.exec(query.order_by(*order)))


# Declared BEFORE "DELETE /{email_id}", or "trash" would be read as an email id (422)
@router.delete("/trash", response_model=EmptyTrashResult, summary="Empty the Trash (permanent)")
def empty_trash(session: SessionDep) -> EmptyTrashResult:
    # The only irreversible delete: the UI asks for confirmation first (story 3.6)
    result = session.exec(delete(Email).where(_in_trash()))  # type: ignore[call-overload]
    session.commit()
    deleted = result.rowcount or 0
    logger.info("Emptied the Trash: %d emails permanently deleted", deleted)
    return EmptyTrashResult(deleted=deleted)


@router.get(
    "/{email_id}",
    response_model=EmailRead,
    summary="Get one email",
    responses={404: {"description": "Email not found"}},
)
def get_email(email_id: int, session: SessionDep) -> Email:
    # Also returns a trashed email (deleted_at set): the reading pane shows it
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
    query = select(func.count()).select_from(Email).where(col(Email.priority).is_(None), _active())
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
        .where(col(Email.priority).is_(None), _active())  # never send trashed emails to Claude
        .order_by(*_newest_order())
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
    # priority (including a manual one). Not for trashed emails.
    email = _get_or_404(session, email_id)
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
    # PATCH = partial update: only the fields that were sent are changed.
    # Trashed emails can't be changed (restore them first).
    email = _get_or_404(session, email_id)

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


@router.delete(
    "/{email_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Move an email to the Trash (can be restored)",
    responses={404: {"description": "Email not found (or already in the Trash)"}},
)
def delete_email(email_id: int, session: SessionDep) -> None:
    # Soft delete: only mark it; DELETE /trash removes it for good
    email = _get_or_404(session, email_id)
    email.deleted_at = datetime.now(UTC)
    session.add(email)
    session.commit()
    logger.info("Moved email %d to the Trash", email_id)


@router.post(
    "/{email_id}/restore",
    response_model=EmailRead,
    summary="Restore an email from the Trash",
    responses={404: {"description": "Email not found in the Trash"}},
)
def restore_email(email_id: int, session: SessionDep) -> Email:
    email = _get_or_404(session, email_id, trashed=True)
    email.deleted_at = None  # every other field was kept, so it comes back unchanged
    session.add(email)
    session.commit()
    session.refresh(email)
    logger.info("Restored email %d from the Trash", email_id)
    return email
