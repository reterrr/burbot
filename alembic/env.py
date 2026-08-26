from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path
from typing import Any

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

# This migration environment is deliberately scoped to business_driver.
# Configure metadata before importing its models so generated constraints have
# deterministic names. Core, extraction and system models are not imported.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
SQLModel.metadata.naming_convention = NAMING_CONVENTION

from business_driver.schemas import entities as _business_entities  # noqa: E402,F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def get_database_url() -> str:
    """Return the application database URL used by Alembic."""

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    configured_url = config.get_main_option("sqlalchemy.url").strip()
    if configured_url:
        return configured_url

    raise RuntimeError(
        "DATABASE_URL is not configured. Set it in the environment or in "
        "the repository-root .env file."
    )


def migration_options() -> dict[str, Any]:
    """Return options shared by online and offline migrations."""

    return {
        "target_metadata": target_metadata,
        "compare_type": True,
        "compare_server_default": True,
    }


def run_migrations_offline() -> None:
    """Render migration SQL without opening a database connection."""

    context.configure(
        url=get_database_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **migration_options(),
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with Alembic's synchronous connection facade."""

    context.configure(connection=connection, **migration_options())

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and hand its connection to Alembic."""

    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations against the configured database."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
