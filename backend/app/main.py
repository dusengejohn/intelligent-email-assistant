"""FastAPI entry point for the Intelligent Email Assistant."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.db import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Runs once at startup (before `yield`) and once at shutdown (after it)
    create_db_and_tables()
    yield


app = FastAPI(title="Intelligent Email Assistant", lifespan=lifespan)
api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api)
