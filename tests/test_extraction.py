import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger, event, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlmodel import SQLModel

os.environ.setdefault("DCKR_DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from business_layer.schemas.models import (  # noqa: E402
    BusinessEntity,
    BusinessEntityField,
    BusinessModel,
    BusinessModelRevision,
    BusinessObject,
    BusinessObjectField,
)
from extraction.exceptions import ExtractionConflict, ExtractionValidationError  # noqa: E402
from extraction.schemas.api import CreateExtractionRunRequest  # noqa: E402
from extraction.schemas.models import (  # noqa: E402
    ConcreteValue,
    ExtractionRun,
    FieldObservation,
)
from extraction.services.extraction import ExtractionService  # noqa: E402
from sources.schemas.enums import SourceState, SourceType  # noqa: E402
from sources.schemas.models import (  # noqa: E402
    Source,
    SourceFieldTracking,
    SourceObjectFieldTracking,
    StoredFile,
)
from tasks.schemas.models import Workflow, WorkflowStatus  # noqa: E402


@compiles(BigInteger, "sqlite")
def sqlite_bigint(_type, _compiler, **_kwargs):
    return "INTEGER"


@compiles(JSONB, "sqlite")
def sqlite_jsonb(_type, _compiler, **_kwargs):
    return "JSON"


pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / f'extraction-{uuid4().hex}.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    tables = [
        BusinessModel.__table__,
        BusinessModelRevision.__table__,
        BusinessEntity.__table__,
        BusinessEntityField.__table__,
        BusinessObject.__table__,
        BusinessObjectField.__table__,
        StoredFile.__table__,
        Source.__table__,
        SourceFieldTracking.__table__,
        SourceObjectFieldTracking.__table__,
        Workflow.__table__,
        ExtractionRun.__table__,
        FieldObservation.__table__,
        ConcreteValue.__table__,
    ]

    try:
        async with engine.begin() as connection:
            await connection.run_sync(lambda conn: SQLModel.metadata.create_all(conn, tables=tables))
        yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def seeded(sessions):
    async with sessions() as session:
        session.add(BusinessModel(id=10, key="funding", name="Funding"))
        await session.flush()
        session.add(BusinessEntity(id=20, business_model_id=10, table_name="projects"))
        await session.flush()
        session.add(BusinessEntityField(id=30, business_entity_id=20))
        session.add(BusinessObject(id=40, business_entity_id=20))
        session.add(BusinessObject(id=41, business_entity_id=20))
        await session.flush()
        session.add(
            BusinessObjectField(
                id=50,
                business_object_id=40,
                business_entity_field_id=30,
            )
        )
        await session.flush()
        session.add(
            Source(
                id=60,
                type=SourceType.HTML,
                url="https://example.com/project",
                state=SourceState.ACTIVE,
            )
        )
        await session.flush()
        session.add(
            SourceFieldTracking(
                id=70,
                source_id=60,
                business_entity_field_id=30,
                tracking_enabled=True,
            )
        )
        await session.flush()
        session.add(
            SourceObjectFieldTracking(
                id=80,
                source_field_tracking_id=70,
                business_object_field_id=50,
                tracking_enabled=True,
                version=1,
            )
        )
        session.add(
            Workflow(
                id=90,
                source_id=60,
                source_snapshot_id=100,
                status=WorkflowStatus.ACTIVE,
            )
        )
        await session.commit()

    return {
        "source_id": 60,
        "snapshot_id": 100,
        "workflow_id": 90,
        "object_id": 40,
        "other_object_id": 41,
        "object_field_id": 50,
        "tracking_version_id": 80,
    }


def request_for(seeded, *, snapshot_id=None, object_id=None):
    return CreateExtractionRunRequest.model_validate(
        {
            "workflow_id": seeded["workflow_id"],
            "field_observations": [
                {
                    "object_id": object_id or seeded["object_id"],
                    "concrete_values": [
                        {
                            "snapshot_id": snapshot_id or seeded["snapshot_id"],
                            "values": [
                                {
                                    "concrete_value": "Generator Kompetencji 3.0",
                                    "char_start": 12,
                                    "char_end": 37,
                                    "token_class_id": "text",
                                    "object_field_id": seeded["object_field_id"],
                                },
                                {
                                    "concrete_value": "GK 3.0",
                                    "char_start": 50,
                                    "char_end": 56,
                                    "token_class_id": "text",
                                    "object_field_id": seeded["object_field_id"],
                                },
                            ],
                        }
                    ],
                }
            ],
        }
    )


async def test_create_run_persists_exact_tracking_version_and_ordered_evidence(sessions, seeded):
    async with sessions() as session:
        response = await ExtractionService(session).create_extraction_run(request_for(seeded))

        assert response.status == "completed"
        assert response.workflow_id == seeded["workflow_id"]
        assert response.source_snapshot_id == seeded["snapshot_id"]
        assert len(response.field_observations) == 1
        observation = response.field_observations[0]
        assert observation.business_object_id == seeded["object_id"]
        assert observation.business_object_field_id == seeded["object_field_id"]
        assert observation.tracking_version_id == seeded["tracking_version_id"]
        assert [value.value_index for value in observation.concrete_values] == [0, 1]
        assert [value.concrete_value for value in observation.concrete_values] == [
            "Generator Kompetencji 3.0",
            "GK 3.0",
        ]

        persisted = await session.scalar(select(FieldObservation))
        assert persisted is not None
        assert persisted.source_field_tracking_id == 70
        assert persisted.source_object_field_tracking_id == seeded["tracking_version_id"]
        assert await session.scalar(select(func.count()).select_from(ConcreteValue)) == 2


async def test_snapshot_mismatch_is_rejected_without_partial_run(sessions, seeded):
    async with sessions() as session:
        with pytest.raises(ExtractionValidationError):
            await ExtractionService(session).create_extraction_run(
                request_for(seeded, snapshot_id=seeded["snapshot_id"] + 1)
            )

        assert await session.scalar(select(func.count()).select_from(ExtractionRun)) == 0
        assert await session.scalar(select(func.count()).select_from(FieldObservation)) == 0


async def test_object_field_must_belong_to_submitted_object(sessions, seeded):
    async with sessions() as session:
        with pytest.raises(ExtractionValidationError):
            await ExtractionService(session).create_extraction_run(
                request_for(seeded, object_id=seeded["other_object_id"])
            )

        assert await session.scalar(select(func.count()).select_from(ExtractionRun)) == 0


async def test_non_active_workflow_rejects_new_evidence(sessions, seeded):
    async with sessions() as session:
        workflow = await session.get(Workflow, seeded["workflow_id"])
        workflow.status = WorkflowStatus.SUPERSEDED
        session.add(workflow)
        await session.commit()

    async with sessions() as session:
        with pytest.raises(ExtractionConflict):
            await ExtractionService(session).create_extraction_run(request_for(seeded))

        assert await session.scalar(select(func.count()).select_from(ExtractionRun)) == 0


async def test_disabled_tracking_rejects_new_evidence(sessions, seeded):
    async with sessions() as session:
        tracking = await session.get(SourceObjectFieldTracking, seeded["tracking_version_id"])
        tracking.tracking_enabled = False
        session.add(tracking)
        await session.commit()

    async with sessions() as session:
        with pytest.raises(ExtractionValidationError):
            await ExtractionService(session).create_extraction_run(request_for(seeded))

        assert await session.scalar(select(func.count()).select_from(ExtractionRun)) == 0
