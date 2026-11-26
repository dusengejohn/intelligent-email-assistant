"""FastAPI entry point for the Email Generator service (Epic 3b).

It only generates sample emails and delivers them to the inbox; it has no
database. The inbox (backend/) receives, stores and triages them.

In the Docker image it also serves its own page (the built `web/`, copied to
`static/`) at `/`: page and API share one origin, so no CORS and one container.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.routers import generate, health
from app.services.errors import AIConfigError, AIServiceError
from app.services.inbox import InboxConfigError, InboxError

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
# The HTTP libraries log every request at INFO; keep only their warnings
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)

# Where the Dockerfile puts the page's build output (absent in dev and tests)
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


# Central error mapping. 503: our side isn't set up; 502: a service we depend on failed.
def ai_config_error(request: Request, exc: AIConfigError) -> JSONResponse:
    return _error(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


def inbox_config_error(request: Request, exc: InboxConfigError) -> JSONResponse:
    return _error(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))


def ai_service_error(request: Request, exc: AIServiceError) -> JSONResponse:
    return _error(status.HTTP_502_BAD_GATEWAY, f"AI service error: {exc}")


def inbox_error(request: Request, exc: InboxError) -> JSONResponse:
    return _error(status.HTTP_502_BAD_GATEWAY, str(exc))


def create_app(static_dir: Path = STATIC_DIR) -> FastAPI:
    """Build the app; serve the page from `static_dir` if it exists."""
    app = FastAPI(title="Email Generator")

    # Every route lives under /api, like the inbox
    api = APIRouter(prefix="/api")
    api.include_router(health.router)
    api.include_router(generate.router)

    # Any other /api/... path is a JSON 404, never the page (declared last, so
    # the real routes above match first)
    @api.api_route(
        "/{path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    def unknown_api_path(path: str) -> None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    app.include_router(api)

    app.add_exception_handler(AIConfigError, ai_config_error)
    app.add_exception_handler(InboxConfigError, inbox_config_error)
    app.add_exception_handler(AIServiceError, ai_service_error)
    app.add_exception_handler(InboxError, inbox_error)

    # Mounted last: it answers only what no API route matched. html=True serves
    # index.html for "/".
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="web")
    return app


app = create_app()
