"""FastAPI entry point for the Email Generator service (Epic 3b).

It only generates sample emails and delivers them to the inbox; it has no
database. The inbox (backend/) receives, stores and triages them.
"""

import logging

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.routers import generate, health
from app.services.errors import AIConfigError, AIServiceError
from app.services.inbox import InboxConfigError, InboxError

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
# The HTTP libraries log every request at INFO; keep only their warnings
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)

app = FastAPI(title="Email Generator")

# Every route lives under /api, like the inbox
api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(generate.router)
app.include_router(api)


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


# Central error mapping. 503: our side isn't set up; 502: a service we depend on failed.
@app.exception_handler(AIConfigError)
def ai_config_error(request: Request, exc: AIConfigError) -> JSONResponse:
    return _error(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


@app.exception_handler(InboxConfigError)
def inbox_config_error(request: Request, exc: InboxConfigError) -> JSONResponse:
    return _error(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


@app.exception_handler(AIServiceError)
def ai_service_error(request: Request, exc: AIServiceError) -> JSONResponse:
    return _error(status.HTTP_502_BAD_GATEWAY, f"AI service error: {exc}")


@app.exception_handler(InboxError)
def inbox_error(request: Request, exc: InboxError) -> JSONResponse:
    return _error(status.HTTP_502_BAD_GATEWAY, str(exc))
