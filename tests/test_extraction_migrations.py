"""Exercise upgrade, legacy preservation, rollback protection and re-upgrade."""

import io
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

ROOT = Path(__file__).resolve().parents[1]


def config(output=None):
    cfg = Config(str(ROOT / "alembic.ini"), output_buffer=output)
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    return cfg


def test_offline_migration_chain_compiles(monkeypatch):
    monkeypatch.setenv("HOST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    output = io.StringIO()
    command.upgrade(config(output), "head", sql=True)
    sql = output.getvalue()
    for fragment in (
        "CREATE TABLE IF NOT EXISTS extraction_runs",
        "CREATE TABLE source_snapshots",
        "CREATE TABLE elements_xlsx",
        "CREATE TABLE extraction_captures",
        "fk_source_object_field_trackings_last_observation_id",
    ):
        assert fragment in sql
    assert "DROP TABLE" not in sql


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.environ.get("EXTRACTION_TEST_DATABASE_URL"), reason="Requires PostgreSQL"
)
async def test_migrations_preserve_legacy_and_protect_capture(monkeypatch):
    url = os.environ["EXTRACTION_TEST_DATABASE_URL"]
    monkeypatch.setenv("HOST_DATABASE_URL", url)
    schema = f"migration_test_{uuid4().hex}"
    admin = create_async_engine(url)
    async with admin.begin() as connection:
        await connection.execute(CreateSchema(schema))
    engine = create_async_engine(
        url, connect_args={"server_settings": {"search_path": f"{schema},public"}}
    )
    cfg = config()
    cfg.attributes["version_table_schema"] = schema

    async def migrate(target, downgrade=False):
        async with engine.begin() as connection:

            def run(sync):
                cfg.attributes["connection"] = sync
                (command.downgrade if downgrade else command.upgrade)(cfg, target)

            await connection.run_sync(run)

    try:
        await migrate("e100_extraction_legacy")
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO workflows (id, key, source_id, source_snapshot_id) "
                    "VALUES (90, 'legacy', 60, 100)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO extraction_runs "
                    "(id, workflow_id, source_id, source_snapshot_id, status) "
                    "VALUES (1, 90, 60, 100, 'completed')"
                )
            )
        async with engine.begin() as connection:
            statements = [
                "INSERT INTO business_models (id, key, name) VALUES (10, 'funding', 'Funding')",
                (
                    "INSERT INTO business_entities (id, business_model_id, table_name) VALUES "
                    "(20, 10, 'projects')"
                ),
                "INSERT INTO business_entity_fields (id, business_entity_id) VALUES (30, 20)",
                "INSERT INTO business_objects (id, business_entity_id) VALUES (40, 20)",
                (
                    "INSERT INTO business_object_fields (id, business_object_id, "
                    "business_entity_field_id) VALUES (50, 40, 30)"
                ),
                "INSERT INTO sources (id, type, url) VALUES (60, 'HTML', 'https://example.org')",
                (
                    "INSERT INTO source_field_trackings (id, source_id, "
                    "business_entity_field_id) VALUES (70, 60, 30)"
                ),
                (
                    "INSERT INTO source_object_field_trackings (id, source_field_tracking_id, "
                    "business_object_field_id) VALUES (80, 70, 50)"
                ),
                (
                    "INSERT INTO field_observations (id, extraction_run_id, "
                    "source_field_tracking_id, source_object_field_tracking_id, "
                    "business_object_id, business_object_field_id) VALUES (100, 1, 70, 80, 40, "
                    "50)"
                ),
                (
                    "INSERT INTO extraction_concrete_values (id, field_observation_id, "
                    "source_snapshot_id, raw_value, char_start, char_end, token_class_id, "
                    "value_index) VALUES (1, 100, 100, '100000', 0, 6, 'text', 0)"
                ),
            ]
            for statement in statements:
                await connection.execute(text(statement))
        await migrate("head")
        async with engine.connect() as connection:
            assert (
                await connection.execute(
                    text("SELECT raw_value FROM extraction_concrete_values WHERE id=1")
                )
            ).scalar_one() == "100000"
            assert (
                await connection.execute(text("SELECT id FROM token_classes WHERE id='text'"))
            ).scalar_one() == "text"
            assert (
                await connection.execute(text("SELECT workflow_id FROM extraction_runs WHERE id=1"))
            ).scalar_one() == 90
        await migrate("e100_extraction_legacy", downgrade=True)
        await migrate("head")
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO extraction_runs (id, source_id, source_snapshot_id, status) "
                    "VALUES (2, 60, 101, 'pending')"
                )
            )
        with pytest.raises(Exception, match="Cannot downgrade"):
            await migrate("e100_extraction_legacy", downgrade=True)
        async with engine.connect() as connection:
            assert (
                await connection.execute(
                    text("SELECT status::text FROM extraction_runs WHERE id=2")
                )
            ).scalar_one() == "pending"
            assert (
                await connection.execute(
                    text("SELECT to_regclass('extraction_captures') IS NOT NULL")
                )
            ).scalar_one()
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await admin.dispose()
