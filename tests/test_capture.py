"""Capture integration tests against real SQL rows (SQLite or isolated PostgreSQL)."""

import asyncio
import copy
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
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
from extraction.api.routes import capture_router
from extraction.exceptions import (
    ExtractionConflict,
    ExtractionNotConfigured,
    ExtractionNotFound,
    ExtractionValidationError,
)
from extraction.schemas import capture as dto
from extraction.schemas.evidence import (
    Element,
    ElementHTML,
    ElementPDF,
    ElementXLSX,
    ExtractionCapture,
    FieldSelector,
    GroundTruth,
    ScopeInstance,
    SourceScope,
    TokenClass,
)
from extraction.schemas.models import (
    EXTRACTION_TABLES,
    ConcreteValue,
    ExtractionRun,
    FieldObservation,
)
from extraction.services.extraction import ExtractionService
from shared.database import get_session
from sources.schemas.enums import SourceState, SourceType
from sources.schemas.models import (
    SOURCE_TABLES,
    Source,
    SourceFieldTracking,
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
                lambda conn: SQLModel.metadata.create_all(conn, tables=tables)
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
                SourceSnapshot(id=100, source_id=60, fetched_at=datetime(2026, 9, 15, tzinfo=UTC))
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
                "selector": {"type": "CSS", "value": "td"},
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


async def test_create_run_and_missing_snapshot(sessions):
    async with sessions() as session:
        service = ExtractionService(session)
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=100, extractor_version="manual")
        )
        assert run.status == "pending" and run.started_at is None and run.snapshot_id == 100
        with pytest.raises(ExtractionNotFound):
            await service.create_run(
                dto.CreateRunRequest(snapshot_id=999, extractor_version="manual")
            )
        assert await count(session, ExtractionRun) == 1


async def test_capture_evidence_ground_truth_and_idempotency(sessions):
    async with sessions() as session:
        data = dto.CaptureRequest.model_validate(capture())
        run, response = await run_capture(session, capture())
        again = await ExtractionService(session).register_capture(run.id, data)
        assert again == response
        assert response.reconciliation_observations == response.resolved_observations
        assert await count(session, ConcreteValue) == await count(session, GroundTruth) == 1
        assert await count(session, ElementHTML) == 3
        assert await count(session, ScopeInstance) == 2
        tracking = await current_tracking(session)
        observation = await session.get(FieldObservation, response.resolved_observations[0])
        assert tracking.baseline_observation_id == observation.id
        assert tracking.version == 2 and tracking.id != observation.source_object_field_tracking_id
        assert await count(session, BusinessObjectFieldValue) == 0
        assert observation.status == "VALIDATED"
        with pytest.raises(ExtractionConflict):
            await ExtractionService(session).register_capture(
                run.id, data.model_copy(update={"capture_key": "different"})
            )


async def test_repeated_and_nested_scopes_multiple_fields(sessions):
    data = capture(rows=2)
    second_field = copy.deepcopy(data["values"][0])
    second_field.update(client_key="end-date", business_entity_field_id=31)
    data["values"].append(second_field)
    # Inputs need not arrive in topological order.
    data["elements"].reverse()
    data["scopes"].reverse()
    data["scope_instances"].reverse()
    async with sessions() as session:
        _, response = await run_capture(session, data)
        assert response.observations_created == 3
        assert await count(session, SourceScope) == 2
        assert await count(session, ScopeInstance) == 3
        assert await count(session, SourceFieldTracking) == 2
        assert await count(session, BusinessObjectField) == 3


@pytest.mark.parametrize("kind", ["PDF", "XLSX"])
async def test_pdf_and_harmonogram_xlsx_capture(sessions, kind):
    data = capture(object_id=None)
    for element in data["elements"]:
        element.pop("html")
        element["element_from"] = kind
        element[kind.lower()] = (
            {"page_number": 1, "x0": 10, "x1": 50, "y0": 20, "y1": 30}
            if kind == "PDF"
            else {"sheet_name": "Harmonogram", "cell_range": "A1:C12"}
        )
    for scope in data["scopes"]:
        scope["selector"] = {
            "type": "PDF_REGION" if kind == "PDF" else "XLSX_RANGE",
            "value": "page=1" if kind == "PDF" else "Harmonogram!A1:C12",
        }
    async with sessions() as session:
        source = await session.get(Source, 60)
        source.type = SourceType(kind)
        await session.commit()
        data["values"][0]["selector"] = data["scopes"][1]["selector"]
        _, response = await run_capture(session, data)
        assert len(response.unresolved_observations) == 1
        assert await count(session, ElementPDF if kind == "PDF" else ElementXLSX) == 3
        assert await count(session, SourceObjectFieldTracking) == 0


async def test_resolve_object_without_second_observation(sessions):
    async with sessions() as session:
        _, response = await run_capture(session, capture(object_id=None))
        obs_id = response.unresolved_observations[0]
        service = ExtractionService(session)
        with pytest.raises(ExtractionValidationError):
            await service.resolve_observation_object(obs_id, 42)
        result = await service.resolve_observation_object(obs_id, 40)
        again = await service.resolve_observation_object(obs_id, 40)
        assert result == again
        assert await count(session, FieldObservation) == 1
        assert result.business_object_id == 40 and result.status == "VALIDATED"
        assert (await current_tracking(session)).baseline_observation_id == obs_id
        with pytest.raises(ExtractionConflict):
            await service.resolve_observation_object(obs_id, 41)


@pytest.mark.parametrize(
    "mutation", ["wrong-field", "wrong-object", "outside-scope", "missing-token", "bad-offset"]
)
async def test_atomic_failure_preserves_failed_run_only(sessions, mutation):
    data = capture()
    if mutation == "wrong-field":
        data["values"][0]["business_entity_field_id"] = 32
    elif mutation == "wrong-object":
        data["scope_instances"][1]["business_object_id"] = 42
    elif mutation == "outside-scope":
        data["values"][0]["element_client_key"] = "doc"
    elif mutation == "missing-token":
        data["values"][0]["token_class_id"] = "unknown"
    else:
        data["values"][0]["char_end"] = 500
    async with sessions() as session:
        service = ExtractionService(session)
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=100, extractor_version="manual")
        )
        with pytest.raises(ExtractionValidationError):
            await service.register_capture(run.id, dto.CaptureRequest.model_validate(data))
        persisted = await session.get(ExtractionRun, run.id)
        assert persisted.status == "failed" and persisted.finished_at and persisted.error_message
        for model in (
            Element,
            ScopeInstance,
            SourceScope,
            SourceFieldTracking,
            SourceObjectFieldTracking,
            ConcreteValue,
            FieldObservation,
            GroundTruth,
            ExtractionCapture,
        ):
            assert await count(session, model) == 0
        # Same run can be retried after fixing the request.
        result = await service.register_capture(
            run.id, dto.CaptureRequest.model_validate(capture())
        )
        assert result.status == "succeeded"


async def test_baseline_compares_source_not_canonical_and_preserves_history(sessions):
    async with sessions() as session:
        _, first = await run_capture(session, capture())
        tracking = await current_tracking(session)
        baseline_id = tracking.baseline_observation_id
        slot = tracking.business_object_field_id
        session.add(BusinessObjectFieldValue(business_object_field_id=slot, value_json=120000))
        await session.commit()
        _, same = await run_capture(session, capture(key="same"))
        assert not same.changed_source_object_fields
        assert (await current_tracking(session)).baseline_observation_id == baseline_id
        assert (await current_tracking(session)).last_changed_at is None
        _, changed = await run_capture(session, capture(key="changed", value="120000"))
        latest = await current_tracking(session)
        assert changed.changed_source_object_fields == [latest.id]
        assert latest.baseline_observation_id == changed.resolved_observations[0]
        assert latest.last_changed_at is not None
        assert (await session.get(FieldObservation, baseline_id)).status == "VALIDATED"
        assert (await session.scalar(select(BusinessObjectFieldValue))).value_json == 120000
        assert await count(session, SourceFieldTracking) == 1
        assert await count(session, BusinessObjectField) == 1


async def test_detected_and_late_evidence_do_not_rewind_baseline(sessions):
    async with sessions() as session:
        _, first = await run_capture(session, capture())
        _, detected = await run_capture(
            session, capture(key="detected", value="90000", confirmed=False)
        )
        tracking = await current_tracking(session)
        assert tracking.baseline_observation_id == first.resolved_observations[0]
        latest_id = tracking.last_observation_id
        session.add(
            SourceSnapshot(id=99, source_id=60, fetched_at=datetime(2026, 9, 1, tzinfo=UTC))
        )
        await session.commit()
        _, late = await run_capture(session, capture(key="late", value="1"), snapshot_id=99)
        tracking = await current_tracking(session)
        assert tracking.last_observation_id == latest_id
        assert tracking.baseline_observation_id == first.resolved_observations[0]
        assert not late.changed_source_object_fields and not detected.reconciliation_observations


async def test_selectors_version_and_scopes_carry_children(sessions):
    async with sessions() as session:
        await run_capture(session, capture())
        await run_capture(session, capture(key="same"))
        assert await count(session, FieldSelector) == 1
        changed = capture(key="selector")
        changed["values"][0]["selector"]["value"] = "td.amount"
        await run_capture(session, changed)
        selectors = list(await session.scalars(select(FieldSelector).order_by(FieldSelector.id)))
        assert [s.version for s in selectors] == [1, 2]
        assert selectors[0].valid_to is not None and selectors[1].valid_to is None
        changed["capture_key"] = "scope"
        changed["scopes"][0]["selector"]["value"] = "body"
        await run_capture(session, changed)
        scopes = list(
            await session.scalars(select(SourceScope).where(SourceScope.valid_to.is_(None)))
        )
        root = next(s for s in scopes if s.name == "ROOT")
        child = next(s for s in scopes if s.name != "ROOT")
        assert child.parent_scope_id == root.id and child.version == root.version == 2


async def test_missing_value_is_issue_not_null(sessions):
    data = capture()
    data["values"] = []
    data["issues"] = [
        {
            "code": "VALUE_NOT_FOUND",
            "message": "End date absent",
            "scope_instance_client_key": "record0",
            "business_entity_field_id": 30,
        }
    ]
    async with sessions() as session:
        _, result = await run_capture(session, data)
        assert result.status == "partial" and result.observations_created == 0
        assert await count(session, ConcreteValue) == 0
        assert await count(session, BusinessObjectFieldValue) == 0


@pytest.mark.parametrize("mutation", ["duplicate", "unknown", "cycle", "missing-root", "format"])
async def test_request_graph_errors(mutation):
    data = capture()
    if mutation == "duplicate":
        data["elements"].append(data["elements"][0])
    elif mutation == "unknown":
        data["values"][0]["scope_instance_client_key"] = "missing"
    elif mutation == "cycle":
        data["elements"][0]["parent_client_key"] = "cell0"
    elif mutation == "missing-root":
        data["scopes"][0]["name"] = "document"
    else:
        data["elements"][0]["element_from"] = "PDF"
    with pytest.raises(ValidationError):
        dto.CaptureRequest.model_validate(data)


async def test_unconfigured_execution_leaves_pending(sessions):
    async with sessions() as session:
        service = ExtractionService(session)
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=100, extractor_version="auto")
        )
        with pytest.raises(ExtractionNotConfigured):
            await service.execute(run.id, "auto")
        assert (await session.get(ExtractionRun, run.id)).status == "pending"


async def test_adapter_uses_same_capture_and_issues(sessions):
    class Adapter:
        async def extract(self, snapshot, definitions, *, capture_key):
            assert snapshot.id == 100 and definitions.scopes
            data = capture(key=capture_key, object_id=None, confirmed=False)
            data["values"][0]["selector"] = None
            data["values"][0]["discovered_by"] = "AUTOMATIC"
            return dto.CaptureRequest.model_validate(data)

    async with sessions() as session:
        await run_capture(session, capture())
        service = ExtractionService(session, Adapter())
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=100, extractor_version="adapter")
        )
        result = await service.execute(run.id, "auto")
        assert result.observations_created == 1 and result.unresolved_observations
        assert await count(session, GroundTruth) == 1
        assert await service.execute(run.id, "auto") == result


async def test_http_capture_and_domain_statuses(sessions):
    app = FastAPI()
    app.include_router(capture_router)

    async def session_override():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (
            await client.post(
                "/extraction/runs", json={"snapshot_id": 999, "extractor_version": "test"}
            )
        ).status_code == 404
        run = (
            await client.post(
                "/extraction/runs", json={"snapshot_id": 100, "extractor_version": "test"}
            )
        ).json()
        assert (
            await client.post(f"/extraction/runs/{run['id']}/execute", json={"capture_key": "auto"})
        ).status_code == 501
        response = await client.post(f"/extraction/runs/{run['id']}/capture", json=capture())
        assert response.status_code == 200, response.text
        conflict = capture(value="2")
        assert (
            await client.post(f"/extraction/runs/{run['id']}/capture", json=conflict)
        ).status_code == 409
        invalid = capture()
        invalid["elements"].append(invalid["elements"][0])
        assert (
            await client.post(f"/extraction/runs/{run['id']}/capture", json=invalid)
        ).status_code == 422


@pytest.mark.skipif(not os.environ.get("EXTRACTION_TEST_DATABASE_URL"), reason="PostgreSQL locking")
async def test_concurrent_capture_retry_returns_same_result(sessions):
    async with sessions() as session:
        run = await ExtractionService(session).create_run(
            dto.CreateRunRequest(snapshot_id=100, extractor_version="test")
        )

    async def submit():
        async with sessions() as session:
            return await ExtractionService(session).register_capture(
                run.id, dto.CaptureRequest.model_validate(capture())
            )

    first, second = await asyncio.gather(submit(), submit())
    assert first == second
    async with sessions() as session:
        assert await count(session, FieldObservation) == 1
        assert await count(session, SourceFieldTracking) == 1


async def test_explicit_supersession_repoints_equal_baseline(sessions):
    async with sessions() as session:
        _, first = await run_capture(session, capture())
        original = first.resolved_observations[0]
        data = capture(key="correction")
        data["values"][0]["supersedes_observation_id"] = original
        _, response = await run_capture(session, data)
        latest = await current_tracking(session)
        assert latest.baseline_observation_id == response.resolved_observations[0]
        assert latest.last_changed_at is None
        assert (await session.get(FieldObservation, original)).status == "SUPERSEDED"
        assert not response.changed_source_object_fields
        assert await count(session, GroundTruth) == 2


async def test_detected_supersession_and_cross_source_capture_are_rejected(sessions):
    async with sessions() as session:
        _, first = await run_capture(session, capture())
        data = capture(key="unreviewed", confirmed=False)
        data["values"][0]["supersedes_observation_id"] = first.resolved_observations[0]
        with pytest.raises(ExtractionValidationError, match="validated"):
            await run_capture(session, data)
        assert (
            await session.get(FieldObservation, first.resolved_observations[0])
        ).status == "VALIDATED"
        run = await ExtractionService(session).create_run(
            dto.CreateRunRequest(snapshot_id=100, extractor_version="test")
        )
        snapshot = await session.get(SourceSnapshot, 100)
        session.add(Source(id=61, type=SourceType.HTML, url="https://example.org/other"))
        await session.flush()
        snapshot.source_id = (
            61  # Deliberately corrupt acquisition linkage to check the domain guard.
        )
        await session.commit()
        with pytest.raises(ExtractionValidationError, match="different sources"):
            await ExtractionService(session).register_capture(
                run.id, dto.CaptureRequest.model_validate(capture(key="wrong-source"))
            )


async def test_explicit_null_and_raw_fallback_are_distinct(sessions):
    async with sessions() as session:
        data = capture(value="brak")
        data["values"][0].update(normalized_value=None, is_semantic_null=True)
        _, first = await run_capture(session, data)
        data["capture_key"] = "literal-brak"
        data["values"][0]["is_semantic_null"] = False
        _, second = await run_capture(session, data)
        assert second.changed_source_object_fields
        assert (
            await session.get(FieldObservation, first.resolved_observations[0])
        ).status == "VALIDATED"


async def test_disabled_binding_preserved_and_same_record_identity_checked(sessions):
    async with sessions() as session:
        await run_capture(session, capture())
        tracking = await current_tracking(session)
        from sources.services.tracking import append_tracking_version

        await append_tracking_version(
            session, tracking, {"tracking_enabled": False}, "Disabled in test"
        )
        await session.commit()
        with pytest.raises(ExtractionConflict, match="disabled"):
            await run_capture(session, capture(key="disabled"))
        assert not (await current_tracking(session)).tracking_enabled


async def test_adapter_failure_marks_failed_without_evidence(sessions):
    class Broken:
        async def extract(self, *_args, **_kwargs):
            raise RuntimeError("parser unavailable")

    async with sessions() as session:
        service = ExtractionService(session, Broken())
        run = await service.create_run(
            dto.CreateRunRequest(snapshot_id=100, extractor_version="broken")
        )
        with pytest.raises(RuntimeError):
            await service.execute(run.id, "broken")
        state = await session.get(ExtractionRun, run.id)
        assert state.status == "failed" and state.finished_at and state.started_at
        assert await count(session, ConcreteValue) == 0


async def test_capture_receipt_and_observation_evidence_http(sessions):
    async with sessions() as session:
        service = ExtractionService(session)
        run, result = await run_capture(session, capture(object_id=None))
        obs_id = result.unresolved_observations[0]
        evidence = await service.capture.get_observation(obs_id)
        assert evidence.concrete_values[0].normalized_value == "100000"
        await service.resolve_observation_object(obs_id, 40)
        # Historical capture receipt and current observation serve different needs.
        assert (await service.capture.get_capture(run.id)).unresolved_observations == [obs_id]
        assert (await service.capture.get_observation(obs_id)).business_object_id == 40
        legacy_read = await service.get_extraction_run(run.id)
        assert legacy_read.field_observations[0].concrete_values[0].concrete_value == "100000"


@pytest.mark.skipif(not os.environ.get("EXTRACTION_TEST_DATABASE_URL"), reason="PostgreSQL locking")
async def test_two_runs_share_tracking_without_duplicates(sessions):
    async with sessions() as session:
        service = ExtractionService(session)
        runs = [
            await service.create_run(
                dto.CreateRunRequest(snapshot_id=100, extractor_version="test")
            )
            for _ in range(2)
        ]

    async def submit(run, key):
        async with sessions() as session:
            return await ExtractionService(session).register_capture(
                run.id, dto.CaptureRequest.model_validate(capture(key=key))
            )

    responses = await asyncio.gather(
        submit(runs[0], "concurrent-1"), submit(runs[1], "concurrent-2")
    )
    assert all(r.status == "succeeded" for r in responses)
    async with sessions() as session:
        assert await count(session, SourceFieldTracking) == 1
        assert await count(session, BusinessObjectField) == 1
        assert await count(session, FieldObservation) == 2
        assert await count(session, FieldSelector) == 1
