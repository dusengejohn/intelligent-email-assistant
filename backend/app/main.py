"""FastAPI entry point for the Intelligent Email Assistant."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.db import migrate_database
from app.routers import calendar, emails, health, planning

# uvicorn only sets up its own loggers; without this, the app's INFO lines
# (e.g. "Ingested 10 emails", "Classified 45 emails") would be silently dropped.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
# Alembic announces its internal plugins at INFO on every startup: noise
logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Runs once at startup (before `yield`) and once at shutdown (after it)
    migrate_database()  # bring the database schema up to date (Alembic)
    yield


app = FastAPI(title="Intelligent Email Assistant", lifespan=lifespan)

# Every route lives under /api (brief §3); nginx and Vite pass /api through unchanged
api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(emails.router)
api.include_router(calendar.router)
api.include_router(planning.router)
app.include_router(api)
