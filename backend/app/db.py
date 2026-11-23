"""Database engine, sessions and migrations.

- The **engine** knows how to connect to the database file (one per app).
- A **session** is one unit of work: add/change objects, then `commit()`.
"""

import logging
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect
from sqlalchemy.engine import make_url
from sqlmodel import Session, create_engine

from app import models  # noqa: F401  (registers the tables on SQLModel.metadata)
from app.config import get_settings

logger = logging.getLogger(__name__)

# backend/alembic.ini, found from this file (works locally and in Docker: /app/alembic.ini)
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
# The first migration: the schema as it was before migrations existed
BASELINE_REVISION = "0001"


@lru_cache
def get_engine() -> Engine:
    """Create the engine once, from settings, making sure the DB folder exists."""
    url = make_url(get_settings().database_url)
    if url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    # FastAPI runs sync endpoints in a thread pool; SQLite refuses to share a
    # connection across threads unless we turn that check off.
    return create_engine(url, connect_args={"check_same_thread": False})


def alembic_config(database_url: str) -> Config:
    """Alembic settings for running migrations from the app (not the CLI)."""
    config = Config(str(ALEMBIC_INI))
    config.attributes["database_url"] = database_url
    config.attributes["configure_logging"] = False  # keep the app's logging setup
    return config


def migrate_database() -> None:
    """Bring the database to the latest schema (runs at startup).

    - New database: the migrations create every table.
    - Database from before migrations existed (tables made by create_all, no
      `alembic_version` table): first *stamp* it at the baseline (records the
      version, runs nothing, touches no data), then apply any newer migrations.
    """
    engine = get_engine()  # also creates the data folder if needed
    url = engine.url.render_as_string(hide_password=False)
    config = alembic_config(url)
    tables = set(inspect(engine).get_table_names())
    if "email" in tables and "alembic_version" not in tables:
        logger.info(
            "Existing database without migration history: stamping baseline %s", BASELINE_REVISION
        )
        command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")
    logger.info("Database schema is up to date")


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed afterwards."""
    with Session(get_engine()) as session:
        yield session
