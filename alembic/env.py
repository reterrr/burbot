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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

# Import the core registry first: it installs the metadata naming convention
# before any table is registered. Feature models use the same SQLModel
# metadata object and must also be imported for Alembic autogeneration.
from schemas.core.db import metadata  # noqa: E402
from business_driver.schemas import entities as _business_entities  # noqa: E402,F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata


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
