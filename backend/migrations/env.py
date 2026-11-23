"""Alembic environment: which database to migrate and which models to compare with.

Used by the CLI (`uv run alembic ...` from backend/) and by the app at startup
(app/db.py `migrate_database()`).
"""

import logging.config
from typing import Any

from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel
from sqlmodel.sql.sqltypes import AutoString

from app import models  # noqa: F401  (registers the tables on SQLModel.metadata)
from app.config import get_settings
from app.models import UTCDateTime

config = context.config

# Configure logging only for the CLI. When the app runs migrations at startup it
# sets configure_logging=False, so its own logging setup (main.py) isn't replaced.
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    logging.config.fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def database_url() -> str:
    # The app passes its URL explicitly; the CLI reads the same settings (.env)
    return config.attributes.get("database_url") or get_settings().database_url


def render_item(type_: str, obj: Any, autogen_context: Any) -> str | bool:
    """Write plain SQLAlchemy types into migration files, never our own classes.

    A migration must keep working forever, even after app code changes, so it may
    not import `app.models`. Our types are stored as these plain types anyway.
    """
    if type_ == "type":
        if isinstance(obj, UTCDateTime):
            return "sa.DateTime()"
        if isinstance(obj, AutoString):
            return f"sa.String(length={obj.length})" if obj.length else "sa.String()"
    return False  # default rendering for everything else


# SQLite can't alter most columns in place: batch mode rebuilds the table safely
COMMON_OPTIONS: dict[str, Any] = {
    "target_metadata": target_metadata,
    "render_as_batch": True,
    "render_item": render_item,
    "compare_type": True,
}


def run_migrations_offline() -> None:
    """`alembic upgrade --sql`: print the SQL instead of running it."""
    context.configure(url=database_url(), literal_binds=True, **COMMON_OPTIONS)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, **COMMON_OPTIONS)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
