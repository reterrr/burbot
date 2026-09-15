"""Capture integration tests against real SQL rows (SQLite or isolated PostgreSQL)."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger, event, func, select
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import SQLModel

os.environ.setdefault("DCKR_DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from business_layer.schemas.models import (
    BusinessEntity,
    BusinessEntityField,
    BusinessModel,
    BusinessModelRevision,
    BusinessObject,
    BusinessObjectField,
    BusinessObjectFieldValue,
)
from extraction.schemas import capture as dto
from extraction.schemas.evidence import (
    TokenClass,
)
from extraction.schemas.models import (
    EXTRACTION_TABLES,
)
from extraction.services.extraction import ExtractionService
from sources.schemas.enums import SourceState, SourceType
from sources.schemas.models import (
    SOURCE_TABLES,
    Source,
    SourceObjectFieldTracking,
    SourceSnapshot,
)
from tasks.schemas.models import Workflow


@compiles(BigInteger, "sqlite")
def sqlite_bigint(_type, _compiler, **_kwargs):
    return "INTEGER"


@compiles(JSONB, "sqlite")
def sqlite_json(_type, _compiler, **_kwargs):
    return "JSON"


@compiles(ExcludeConstraint, "sqlite")
def sqlite_exclusion(_constraint, _compiler, **_kwargs):
    # Canonical-value overlap rules are tested in PostgreSQL. Here the table
    # only proves extraction never reads or writes canonical business values.
    return "CHECK (1)"


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def sessions(tmp_path):
    url = os.environ.get("EXTRACTION_TEST_DATABASE_URL")
    admin = schema = None
    if url:
        schema = f"extraction_test_{uuid4().hex}"
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(CreateSchema(schema))
        engine = create_async_engine(
            url, connect_args={"server_settings": {"search_path": f"{schema},public"}}
        )
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'capture.db'}")

        @event.listens_for(engine.sync_engine, "connect")
        def foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

    tables = [
        BusinessModel.__table__,
        BusinessModelRevision.__table__,
        BusinessEntity.__table__,
        BusinessEntityField.__table__,
        BusinessObject.__table__,
        BusinessObjectField.__table__,
        BusinessObjectFieldValue.__table__,
        Workflow.__table__,
        *SOURCE_TABLES,
        *EXTRACTION_TABLES,
    ]
    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda conn: SQLModel.metadata.create_all(conn, tables=tables, checkfirst=False)
            )
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
        async with factory() as session:
            session.add(BusinessModel(id=10, key="funding", name="Funding"))
            await session.flush()
            session.add_all(
                [
                    BusinessEntity(id=20, business_model_id=10, table_name="recruitments"),
                    BusinessEntity(id=21, business_model_id=10, table_name="projects"),
                ]
            )
            await session.flush()
            session.add_all(
                [
                    BusinessEntityField(id=30, business_entity_id=20),
                    BusinessEntityField(id=31, business_entity_id=20),
                    BusinessEntityField(id=32, business_entity_id=21),
                    BusinessObject(id=40, business_entity_id=20),
                    BusinessObject(id=41, business_entity_id=20),
                    BusinessObject(id=42, business_entity_id=21),
                ]
            )
            session.add(
                Source(
                    id=60,
                    type=SourceType.HTML,
                    url="https://example.org/downloads",
                    state=SourceState.ACTIVE,
                )
            )
            session.add(TokenClass(id="text", name="Text"))
            await session.flush()
            session.add(
                SourceSnapshot(
                    id=100,
                    source_id=60,
                    fetched_at=datetime(2026, 9, 15, tzinfo=UTC),
                    page_url="https://example.org/downloads",
                )
            )
            await session.commit()
        yield factory
    finally:
        await engine.dispose()
        if admin:
            async with admin.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
            await admin.dispose()


def capture(*, key="capture-1", value="100000", object_id=40, confirmed=True, rows=1):
    result = {
        "capture_key": key,
        "scopes": [
            {
                "client_key": "document",
                "name": "ROOT",
                "selector": {"type": "CSS", "value": "html"},
            },
            {
                "client_key": "rows",
                "parent_client_key": "document",
                "name": "Recruitment row",
                "business_entity_id": 20,
                "selector": {"type": "CSS", "value": "tr"},
            },
        ],
        "elements": [{"client_key": "doc", "element_from": "HTML", "html": {"tag_name": "html"}}],
        "scope_instances": [
            {"client_key": "root", "scope_client_key": "document", "root_element_client_key": "doc"}
        ],
        "values": [],
    }
    for i in range(rows):
        result["elements"].extend(
            [
                {
                    "client_key": f"row{i}",
                    "parent_client_key": "doc",
                    "element_from": "HTML",
                    "html": {"tag_name": "tr"},
                },
                {
                    "client_key": f"cell{i}",
                    "parent_client_key": f"row{i}",
                    "element_from": "HTML",
                    "text_content": value,
                    "html": {"tag_name": "td"},
                },
            ]
        )
        result["scope_instances"].append(
            {
                "client_key": f"record{i}",
                "parent_client_key": "root",
                "scope_client_key": "rows",
                "root_element_client_key": f"row{i}",
                "occurrence_index": i,
                "business_object_id": (object_id + i) if object_id is not None else None,
            }
        )
        result["values"].append(
            {
                "client_key": f"value{i}",
                "scope_instance_client_key": f"record{i}",
                "element_client_key": f"cell{i}",
                "business_entity_field_id": 30,
                "token_class_id": "text",
                "raw_value": value,
                "normalized_value": value,
                "char_start": 0,
                "char_end": len(value),
                "confirmed_by_human": confirmed,
                "rule": {
                    "selector": {"type": "CSS", "value": "td"},
                    "extraction": {"type": "text"},
                },
            }
        )
    return result


async def run_capture(session, data, *, snapshot_id=100):
    service = ExtractionService(session)
    run = await service.create_run(
        dto.CreateRunRequest(snapshot_id=snapshot_id, extractor_version="firefox-v1")
    )
    return run, await service.register_capture(run.id, dto.CaptureRequest.model_validate(data))


async def current_tracking(session):
    return await session.scalar(
        select(SourceObjectFieldTracking).where(SourceObjectFieldTracking.valid_to.is_(None))
    )


async def count(session, model):
    return await session.scalar(select(func.count()).select_from(model))
