"""Database engine and sessions.

- The **engine** knows how to connect to the database file (one per app).
- A **session** is one unit of work: add/change objects, then `commit()`.
"""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  (registers the tables on SQLModel.metadata)
from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create the engine once, from settings, making sure the DB folder exists."""
    url = make_url(get_settings().database_url)
    if url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    # FastAPI runs sync endpoints in a thread pool; SQLite refuses to share a
    # connection across threads unless we turn that check off.
    return create_engine(url, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    """Create missing tables (existing tables and data are left untouched)."""
    SQLModel.metadata.create_all(get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed afterwards."""
    with Session(get_engine()) as session:
        yield session
