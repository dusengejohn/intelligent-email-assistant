"""FastAPI entry point for the Intelligent Email Assistant."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.db import create_db_and_tables
from app.routers import emails, health
from app.services.errors import AIConfigError, AIServiceError

# uvicorn only sets up its own loggers; without this, the app's INFO lines
# (e.g. Claude token usage per call) would be silently dropped.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
# The SDK's HTTP library logs every request at INFO; keep only its warnings
logging.getLogger("httpx2").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Runs once at startup (before `yield`) and once at shutdown (after it)
    create_db_and_tables()
    yield


app = FastAPI(title="Intelligent Email Assistant", lifespan=lifespan)

# Every route lives under /api (brief §3); nginx and Vite pass /api through unchanged
api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(emails.router)
app.include_router(api)


# Central error mapping: every endpoint (and dependency) answers the same way.
# The messages are short and safe by design (see services/errors.py).
@app.exception_handler(AIConfigError)
def ai_config_error(request: Request, exc: AIConfigError) -> JSONResponse:
    # 503 Service Unavailable: our side isn't set up to use the AI
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(exc)}
    )


@app.exception_handler(AIServiceError)
def ai_service_error(request: Request, exc: AIServiceError) -> JSONResponse:
    # 502 Bad Gateway: the upstream service we depend on (Claude) failed
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": f"AI service error: {exc}"}
    )
