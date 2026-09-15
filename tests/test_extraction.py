"""The public facade has one write pipeline; historical evidence remains readable."""

import pytest
from extraction_support import capture, count, run_capture
from extraction_support import sessions as extraction_sessions
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from extraction.api.routes import capture_router, router
from extraction.exceptions import ExtractionConflict, ExtractionValidationError
from extraction.schemas import api as history_dto
from extraction.schemas import capture as dto
from extraction.schemas.evidence import FieldSelector
from extraction.schemas.models import ConcreteValue, ExtractionRun, FieldObservation
from extraction.services.extraction import ExtractionService
from shared.database import get_session
from sources.schemas.enums import SourceState
from sources.schemas.models import Source
from tasks.schemas.models import Workflow, WorkflowStatus

sessions = extraction_sessions
pytestmark = pytest.mark.asyncio


async def test_workflow_run_uses_canonical_capture(sessions):
    async with sessions() as session:
        session.add(Workflow(id=90, source_id=60, source_snapshot_id=100))
        await session.commit()
        service = ExtractionService(session)
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=100, workflow_id=90, extractor_version="firefox")
        )
        response = await service.register_capture(
            run.id, dto.CaptureRequest.model_validate(capture())
        )
        assert response.status == "succeeded"
        assert (await service.get_run(run.id)).workflow_id == 90
        assert await service.get_capture(run.id) == response
        assert await count(session, FieldSelector) == await count(session, FieldObservation) == 1
        value = await session.scalar(select(ConcreteValue))
        assert value.element_id is not None and value.field_observation_id is None
        assert not hasattr(service, "create_extraction_run")


@pytest.mark.parametrize("invalid", ["snapshot", "workflow", "source"])
async def test_run_preconditions_preserve_no_partial_run(sessions, invalid):
    async with sessions() as session:
        session.add(
            Workflow(
                id=90,
                source_id=60,
                source_snapshot_id=999 if invalid == "snapshot" else 100,
                status=WorkflowStatus.SUPERSEDED
                if invalid == "workflow"
                else WorkflowStatus.ACTIVE,
            )
        )
        if invalid == "source":
            source = await session.get(Source, 60)
            source.state = SourceState.ARCHIVED
        await session.commit()
        with pytest.raises((ExtractionConflict, ExtractionValidationError)):
            await ExtractionService(session).create_run(
                dto.CreateRunRequest(snapshot_id=100, workflow_id=90, extractor_version="firefox")
            )
        assert await count(session, ExtractionRun) == 0


async def test_old_post_is_deprecated_alias_and_rejects_evidence_only_shape(sessions):
    app = FastAPI()
    app.include_router(router)
    app.include_router(capture_router)

    async def session_override():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    assert app.openapi()["paths"]["/extractions"]["post"]["deprecated"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        obsolete = await client.post(
            "/extractions", json={"workflow_id": 90, "field_observations": []}
        )
        assert obsolete.status_code == 422
        async with sessions() as session:
            assert await count(session, ExtractionRun) == 0
        created = await client.post(
            "/extractions", json={"snapshot_id": 100, "extractor_version": "firefox"}
        )
        assert created.status_code == 201 and created.json()["status"] == "pending"
        run_id = created.json()["id"]
        result = await client.post(f"/extraction/runs/{run_id}/capture", json=capture())
        assert result.status_code == 200 and result.json()["observations_created"] == 1
        # GET compatibility also reads the new evidence representation.
        read = await client.get(f"/extractions/{run_id}")
        assert read.status_code == 200
        assert (
            read.json()["field_observations"][0]["concrete_values"][0]["concrete_value"] == "100000"
        )


async def test_historical_completed_run_and_ordered_literals_remain_readable(sessions):
    async with sessions() as session:
        _, captured = await run_capture(session, capture())
        existing = await session.get(FieldObservation, captured.resolved_observations[0])
        session.add(Workflow(id=90, source_id=60, source_snapshot_id=100))
        await session.flush()
        # Seed a historical row, not an alternative production writer.
        legacy = ExtractionRun(
            workflow_id=90, source_id=60, source_snapshot_id=100, status="completed"
        )
        session.add(legacy)
        await session.flush()
        observation = FieldObservation(
            extraction_run_id=legacy.id,
            source_field_tracking_id=existing.source_field_tracking_id,
            source_object_field_tracking_id=existing.source_object_field_tracking_id,
            business_object_id=existing.business_object_id,
            business_object_field_id=existing.business_object_field_id,
        )
        session.add(observation)
        await session.flush()
        for index, raw in enumerate(["Generator Kompetencji 3.0", "GK 3.0"]):
            session.add(
                ConcreteValue(
                    field_observation_id=observation.id,
                    source_snapshot_id=100,
                    raw_value=raw,
                    char_start=0,
                    char_end=len(raw),
                    token_class_id="text",
                    value_index=index,
                )
            )
        await session.commit()
        service = ExtractionService(session)
        result = await service.get_extraction_run(legacy.id)
        assert result.status == "completed"
        assert [v.concrete_value for v in result.field_observations[0].concrete_values] == [
            "Generator Kompetencji 3.0",
            "GK 3.0",
        ]
        page = await service.list_extraction_runs(history_dto.Pagination(), workflow_id=90)
        assert page.total == 1 and page.items[0].id == legacy.id
