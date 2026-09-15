"""API and transaction checks; optionally run against a dedicated PostgreSQL test DB."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlmodel import SQLModel

os.environ.setdefault("DCKR_DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")

from sqlalchemy import BigInteger  # noqa: E402
from sqlalchemy.dialects.postgresql import JSONB  # noqa: E402
from sqlalchemy.ext.compiler import compiles  # noqa: E402

from business_layer.schemas.models import (  # noqa: E402
    BusinessEntity,
    BusinessEntityField,
    BusinessModel,
    BusinessModelRevision,
    BusinessObject,
    BusinessObjectField,
)
from shared.database import get_session  # noqa: E402
from sources.api.routes import router  # noqa: E402
from sources.exceptions import SourceConflict, SourceValidationError  # noqa: E402
from sources.schemas.api import (  # noqa: E402
    SourceCreateRequest,
    SourceObjectFieldTrackingCreate,
    SourceObjectFieldTrackingUpdate,
    SourceStateChangeRequest,
)
from sources.schemas.internal import TrackingObservationUpdate  # noqa: E402
from sources.schemas.models import (  # noqa: E402
    SOURCE_TABLES,
    Source,
    SourceBusinessObject,
    SourceFieldTracking,
    SourceObjectFieldTracking,
    SourceStateHistory,
)


@compiles(BigInteger, "sqlite")
def sqlite_bigint(_type, _compiler, **_kwargs):
    return "INTEGER"


@compiles(JSONB, "sqlite")
def sqlite_jsonb(_type, _compiler, **_kwargs):
    return "JSON"


from sources.services.sources import SourcesService  # noqa: E402
from extraction.schemas.models import EXTRACTION_TABLES, ExtractionRun, FieldObservation  # noqa: E402
from tasks.schemas.models import Workflow  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def sessions(tmp_path):
    url = os.environ.get("SOURCES_TEST_DATABASE_URL")
    admin = None
    schema = None
    if url:
        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError("SOURCES_TEST_DATABASE_URL must use postgresql+asyncpg")
        # Isolate tests from existing data, including other Burbot tables and enum types.
        schema = f"sources_test_{uuid4().hex}"
        admin = create_async_engine(url)
        async with admin.begin() as connection:
            await connection.execute(CreateSchema(schema))
        engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sources.db'}")

        @event.listens_for(engine.sync_engine, "connect")
        def enable_foreign_keys(connection, _record):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(
                lambda conn: SQLModel.metadata.create_all(
                    conn,
                    tables=[
                        BusinessModel.__table__,
                        BusinessModelRevision.__table__,
                        BusinessEntity.__table__,
                        BusinessEntityField.__table__,
                        BusinessObject.__table__,
                        BusinessObjectField.__table__,
                        *SOURCE_TABLES,
                        Workflow.__table__,
                        *EXTRACTION_TABLES,
                    ],
                )
            )
        yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()
        if admin is not None:
            async with admin.begin() as connection:
                await connection.execute(DropSchema(schema, cascade=True))
            await admin.dispose()


@pytest_asyncio.fixture
async def client(sessions):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def session_override():
        async with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test/api/v1"
    ) as client:
        yield client


async def register(client, url="https://example.com/page", type="HTML", **extra):
    response = await client.post("/sources", json={"url": url, "type": type, **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def test_registration_is_persistent_and_undiscovered(client):
    source = await register(client, "HTTPS://EXAMPLE.COM:443/page#section")
    assert source["url"] == "https://example.com/page"
    assert source["state"] == "UNDISCOVERED"
    assert source["file_id"] is None
    assert source["created_at"] == source["last_state_change_at"]
    read = await client.get(f"/sources/{source['id']}")
    assert read.json()["url"] == source["url"]
    history = (await client.get(f"/sources/{source['id']}/state-history")).json()
    assert history["total"] == 1
    assert history["items"][0]["from_state"] is None
    assert history["items"][0]["to_state"] == "UNDISCOVERED"
    assert history["items"][0]["triggered_by"] == "USER"


async def test_duplicate_registration_rolls_back_and_session_remains_usable(sessions):
    async with sessions() as session:
        service = SourcesService(session)
        await service.create_source(SourceCreateRequest(url="https://example.com", type="HTML"))
        with pytest.raises(SourceConflict):
            await service.create_source(
                SourceCreateRequest(
                    url="https://EXAMPLE.com:443/#other",
                    type="PDF",
                )
            )
        await service.create_source(SourceCreateRequest(url="https://example.org", type="HTML"))
        assert await session.scalar(select(func.count()).select_from(Source)) == 2
        assert await session.scalar(select(func.count()).select_from(SourceStateHistory)) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"url": "file:///etc/passwd", "type": "HTML"},
        {"url": "https://user:password@example.com", "type": "HTML"},
        {"url": "https://example.com", "type": "CSV"},
        {"url": "https://example.com", "type": "HTML", "state": "ACTIVE"},
        {"url": "https://example.com", "type": "HTML", "file_id": 0},
        {"url": "https://example.com/" + "a" * 2049, "type": "HTML"},
    ],
)
async def test_invalid_registration_returns_422_without_writes(client, payload):
    assert (await client.post("/sources", json=payload)).status_code == 422
    assert (await client.get("/sources")).json()["total"] == 0


async def test_listing_filters_counts_and_pagination(client):
    first = await register(client)
    second = await register(client, "https://example.com/second")
    await register(client, "https://example.com/document.pdf", "PDF")
    response = await client.get("/sources", params={"type": "HTML", "offset": 1, "limit": 1})
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert [item["id"] for item in response.json()["items"]] == [second["id"]]
    response = await client.get("/sources", params={"url": "HTTPS://EXAMPLE.COM:443/page#section"})
    assert [item["id"] for item in response.json()["items"]] == [first["id"]]
    assert (await client.get("/sources", params={"state": "ACTIVE"})).json()["total"] == 0
    for params in ({"offset": -1}, {"limit": 0}, {"limit": 101}, {"state": "INVALID"}):
        assert (await client.get("/sources", params=params)).status_code == 422


async def test_file_reference_validation(client):
    response = await client.post(
        "/sources/stored-files",
        json={
            "storage_key": "test/pdf",
            "mime_type": "application/pdf",
            "sha256": "a" * 64,
        },
    )
    assert response.status_code == 201
    file_id = response.json()["id"]
    assert "purged_at" not in response.json()
    assert (await client.get(f"/sources/stored-files/{file_id}")).status_code == 200
    for invalid_id, kind in ((999999, "PDF"), (file_id, "HTML")):
        response = await client.post(
            "/sources",
            json={
                "type": kind,
                "file_id": invalid_id,
            },
        )
        assert response.status_code == 422
    source = await register(client, None, "PDF", file_id=file_id)
    assert source["url"] is None and source["file_id"] == file_id
    assert source["type"] == "PDF" and "source_type" not in source
    path = f"/sources/{source['id']}"
    # Removing the only locator must not orphan the source.
    assert (await client.patch(path, json={"file_id": None})).status_code == 422
    response = await client.patch(
        path, json={"url": "https://example.com/file.pdf", "file_id": None}
    )
    assert response.status_code == 200 and response.json()["file_id"] is None
    assert (await client.post("/sources", json={"type": "HTML"})).status_code == 422
    assert (
        await client.post(
            "/sources/stored-files",
            json={
                "storage_key": "test/pdf",
                "mime_type": "application/pdf",
            },
        )
    ).status_code == 409
    assert (
        await client.post(
            "/sources/stored-files",
            json={
                "storage_key": "test/bad",
                "mime_type": "application/pdf",
                "size_bytes": -1,
            },
        )
    ).status_code == 422


async def test_updates_detect_conflicts_and_preserve_existing_data(client):
    first = await register(client)
    second = await register(client, "https://example.com/second")
    path = f"/sources/{second['id']}"
    response = await client.patch(path, json={"url": first["url"]})
    assert response.status_code == 409
    assert (await client.get(path)).json()["url"] == second["url"]
    for payload in ({}, {"url": None}, {"type": None}, {"state": "ACTIVE"}):
        assert (await client.patch(path, json=payload)).status_code == 422
    response = await client.patch(path, json={"url": "https://example.org/new", "type": "PDF"})
    assert response.status_code == 200
    assert response.json()["type"] == "PDF"
    assert (
        await client.put(
            path + "/state",
            json={
                "expected_state": "UNDISCOVERED",
                "state": "DISCOVERING",
            },
        )
    ).status_code == 200
    assert (await client.patch(path, json={"type": "HTML"})).status_code == 409


async def test_lifecycle_history_and_archive(client):
    source = await register(client)
    path = f"/sources/{source['id']}"
    # Skipping discovery/validation and acting on stale state are conflicts.
    assert (
        await client.put(
            path + "/state",
            json={
                "expected_state": "UNDISCOVERED",
                "state": "ACTIVE",
            },
        )
    ).status_code == 409
    previous = "UNDISCOVERED"
    for target in ("DISCOVERING", "VALIDATING", "ACTIVE"):
        response = await client.put(
            path + "/state",
            json={
                "expected_state": previous,
                "state": target,
                "triggered_by": "SYSTEM",
            },
        )
        assert response.status_code == 200
        assert response.json()["state"] == target
        previous = target
    assert (
        await client.put(
            path + "/state",
            json={
                "expected_state": "UNDISCOVERED",
                "state": "DISCOVERING",
            },
        )
    ).status_code == 409
    last_change = (await client.get(path)).json()["last_state_change_at"]
    assert (
        await client.put(
            path + "/state",
            json={
                "expected_state": "ACTIVE",
                "state": "ACTIVE",
            },
        )
    ).status_code == 200
    assert (await client.get(path)).json()["last_state_change_at"] == last_change
    for _ in range(2):
        response = await client.delete(path)
        assert response.status_code == 204
        assert response.content == b""
    assert (await client.get(path)).json()["state"] == "ARCHIVED"
    history = (await client.get(path + "/state-history")).json()
    assert history["total"] == 5
    assert [item["to_state"] for item in history["items"]] == [
        "UNDISCOVERED",
        "DISCOVERING",
        "VALIDATING",
        "ACTIVE",
        "ARCHIVED",
    ]
    page = (await client.get(path + "/state-history", params={"offset": 3, "limit": 1})).json()
    assert page["total"] == 5 and page["items"][0]["to_state"] == "ACTIVE"
    assert (
        await client.put(
            path + "/state",
            json={
                "expected_state": "ARCHIVED",
                "state": "UNDISCOVERED",
            },
        )
    ).status_code == 409


async def test_missing_sources_return_404(client):
    for response in (
        await client.get("/sources/999"),
        await client.get("/sources/999/state-history"),
        await client.patch("/sources/999", json={"type": "PDF"}),
        await client.put(
            "/sources/999/state",
            json={
                "state": "DISCOVERING",
                "expected_state": "UNDISCOVERED",
            },
        ),
        await client.delete("/sources/999"),
    ):
        assert response.status_code == 404


async def test_failed_history_insert_rolls_back_source_and_state(sessions):
    async with sessions() as session:
        fail_history = True

        @event.listens_for(session.sync_session, "before_flush")
        def break_history(db_session, _context, _instances):
            if fail_history:
                for row in db_session.new:
                    if isinstance(row, SourceStateHistory):
                        row.to_state = None

        service = SourcesService(session)
        request = SourceCreateRequest(url="https://example.com", type="HTML")
        with pytest.raises(IntegrityError):
            await service.create_source(request)
        assert await session.scalar(select(func.count()).select_from(Source)) == 0
        fail_history = False
        source = await service.create_source(request)
        fail_history = True
        with pytest.raises(IntegrityError):
            await service.change_state(
                source.id,
                SourceStateChangeRequest(
                    state="DISCOVERING",
                    expected_state="UNDISCOVERED",
                ),
            )
        assert (await service.get_source(source.id)).state == "UNDISCOVERED"
        assert await session.scalar(select(func.count()).select_from(SourceStateHistory)) == 1


@pytest.mark.skipif(not os.environ.get("SOURCES_TEST_DATABASE_URL"), reason="Requires PostgreSQL")
async def test_concurrent_registration_and_transitions(sessions):
    async def register_source():
        async with sessions() as session:
            return await SourcesService(session).create_source(
                SourceCreateRequest(
                    url="https://example.com",
                    type="HTML",
                )
            )

    results = await asyncio.gather(register_source(), register_source(), return_exceptions=True)
    assert sum(isinstance(result, SourceConflict) for result in results) == 1
    source = next(result for result in results if not isinstance(result, Exception))

    async def transition(target):
        async with sessions() as session:
            return await SourcesService(session).change_state(
                source.id,
                SourceStateChangeRequest(
                    state=target,
                    expected_state="UNDISCOVERED",
                ),
            )

    results = await asyncio.gather(
        transition("DISCOVERING"),
        transition("SUSPENDED"),
        return_exceptions=True,
    )
    assert sum(isinstance(result, SourceConflict) for result in results) == 1
    assert sum(not isinstance(result, Exception) for result in results) == 1
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(SourceStateHistory)) == 2


async def test_recovery_cannot_rewrite_source_identity(client):
    source = await register(client)
    path = f"/sources/{source['id']}"
    previous = "UNDISCOVERED"
    for target in ("DISCOVERING", "FAILED", "UNDISCOVERED"):
        response = await client.put(
            path + "/state",
            json={
                "expected_state": previous,
                "state": target,
            },
        )
        assert response.status_code == 200
        previous = target
    response = await client.patch(path, json={"url": "https://example.org/different"})
    assert response.status_code == 409
    assert (await client.get(path)).json()["url"] == source["url"]


@pytest_asyncio.fixture
async def business(sessions):
    async with sessions() as session:
        session.add(BusinessModel(id=10, key="funding", name="Funding"))
        await session.flush()
        session.add_all(
            [
                BusinessEntity(id=20, business_model_id=10, table_name="projects"),
                BusinessEntity(id=21, business_model_id=10, table_name="operators"),
            ]
        )
        await session.flush()
        session.add_all(
            [
                BusinessEntityField(id=30, business_entity_id=20),
                BusinessEntityField(id=31, business_entity_id=20),
                BusinessObject(id=40, business_entity_id=20),
                BusinessObject(id=41, business_entity_id=20),
                BusinessObject(id=42, business_entity_id=21),
            ]
        )
        await session.flush()
        session.add_all(
            [
                BusinessObjectField(id=50, business_object_id=40, business_entity_field_id=30),
                BusinessObjectField(id=51, business_object_id=41, business_entity_field_id=30),
                BusinessObjectField(id=52, business_object_id=40, business_entity_field_id=31),
                # Bad legacy slot: checks in Layer 2 must also detect its entity mismatch.
                BusinessObjectField(id=53, business_object_id=42, business_entity_field_id=30),
            ]
        )
        await session.commit()


async def track(client, source_id, object_field_id=50, **extra):
    path = f"/sources/{source_id}/object-field-trackings"
    response = await client.post(path, json={"business_object_field_id": object_field_id, **extra})
    assert response.status_code == 201, response.text
    return response.json(), path


async def test_metadata_and_source_level_schedule(client, business):
    source = await register(client)
    path = f"/sources/{source['id']}"
    metadata = await client.get(path + "/metadata")
    assert metadata.status_code == 200 and metadata.json()["latest_content_hash"] is None
    assert (await client.get(path + "/check-schedule")).status_code == 404
    response = await client.put(
        path + "/metadata",
        json={
            "latest_content_hash": "abc123",
            "latest_structure_hash": "def456",
        },
    )
    assert response.status_code == 200
    assert response.json()["hashes_updated_at"] is not None
    assert (await client.get(path + "/metadata")).json()["latest_structure_hash"] == "def456"
    assert (
        await client.put(path + "/check-schedule", json={"interval_seconds": 0})
    ).status_code == 422
    assert (
        await client.put(
            path + "/check-schedule",
            json={
                "interval_seconds": 300,
                "last_checked_at": "2026-09-09T12:00:00Z",
                "next_check_at": "2026-09-09T11:00:00Z",
            },
        )
    ).status_code == 422
    response = await client.put(path + "/check-schedule", json={"interval_seconds": 1800})
    assert response.status_code == 200 and response.json()["enabled"]
    await track(client, source["id"])
    response = await client.post(
        path + "/object-field-trackings",
        json={
            "business_object_field_id": 52,
            "desired_refresh_seconds": 300,
        },
    )
    assert response.status_code == 201
    # Demand does not create per-field fetch jobs or overwrite the source cadence.
    assert (await client.get(path + "/check-schedule")).json()["interval_seconds"] == 1800
    assert (await client.get(path)).json()["state"] == "UNDISCOVERED"


async def test_warnings_have_scoped_lifecycle(client):
    source = await register(client)
    other = await register(client, "https://example.org")
    path = f"/sources/{source['id']}/warnings"
    response = await client.post(
        path, json={"description": "Selector missing", "details_json": {"attempt": 1}}
    )
    assert response.status_code == 201
    warning = response.json()
    assert warning["status"] == "OPEN" and warning["resolved_at"] is None
    assert (
        await client.patch(
            f"/sources/{other['id']}/warnings/{warning['id']}", json={"status": "RESOLVED"}
        )
    ).status_code == 404
    response = await client.patch(path + f"/{warning['id']}", json={"status": "RESOLVED"})
    assert response.status_code == 200 and response.json()["resolved_at"] is not None
    assert (await client.get(path, params={"status": "OPEN"})).json()["total"] == 0
    assert (await client.get(path, params={"status": "RESOLVED"})).json()["total"] == 1
    response = await client.patch(path + f"/{warning['id']}", json={"status": "OPEN"})
    assert response.json()["resolved_at"] is None
    assert (await client.post(path, json={"description": "  "})).status_code == 422


async def test_tracking_creates_and_reuses_internal_context(client, business, sessions):
    source = await register(client)
    first, path = await track(client, source["id"], desired_refresh_seconds=300)
    second, _ = await track(client, source["id"], 51, desired_refresh_seconds=60)
    await track(client, source["id"], 52)
    assert "source_field_tracking_id" not in first
    assert first["source_id"] == source["id"] and first["version"] == 1
    assert first["is_current"] and first["valid_to"] is None
    async with sessions() as session:
        parents = list(await session.scalars(select(SourceFieldTracking)))
        assert len(parents) == 2
        assert (
            next(p for p in parents if p.business_entity_field_id == 30).desired_refresh_seconds
            == 60
        )
        assert await session.scalar(select(func.count()).select_from(SourceBusinessObject)) == 2
    response = await client.get(path, params={"business_object_id": 40, "limit": 1})
    assert response.json()["total"] == 2 and len(response.json()["items"]) == 1
    response = await client.get(path, params={"business_object_field_id": 50})
    assert response.json()["total"] == 1 and response.json()["items"][0]["id"] == first["id"]
    await client.delete(path + f"/{second['id']}", params={"expected_version": 1})
    async with sessions() as session:
        parent = await session.scalar(
            select(SourceFieldTracking).where(SourceFieldTracking.business_entity_field_id == 30)
        )
        assert parent.tracking_enabled and parent.desired_refresh_seconds == 300
    await client.delete(path + f"/{first['id']}", params={"expected_version": 1})
    async with sessions() as session:
        parent = await session.scalar(
            select(SourceFieldTracking).where(SourceFieldTracking.business_entity_field_id == 30)
        )
        assert not parent.tracking_enabled and parent.desired_refresh_seconds is None


async def test_internal_tracking_and_link_routes_are_absent(client):
    spec = (await client.get("http://test/openapi.json")).json()
    for path in spec["paths"]:
        assert "/business-objects" not in path
        assert "/business-entities" not in path
        assert "/field-trackings" not in path
    for name in spec["components"]["schemas"]:
        assert not name.startswith(
            ("SourceFieldTracking", "SourceBusinessObject", "SourceBusinessEntity")
        )
    source = await register(client)
    for path, payload in (
        (f"/sources/{source['id']}/field-trackings", {"business_entity_field_id": 30}),
        (f"/sources/{source['id']}/business-objects/40", {}),
        (
            f"/sources/{source['id']}/field-trackings/1/object-field-trackings",
            {"business_object_field_id": 50},
        ),
    ):
        assert (await client.post(path, json=payload)).status_code == 404


async def test_tracking_validates_business_identity_and_source_ownership(
    client, business, sessions
):
    source = await register(client)
    other = await register(client, "https://example.org")
    child, path = await track(client, source["id"])
    assert (await client.post(path, json={"business_object_field_id": 50})).status_code == 409
    assert (await client.post(path, json={"business_object_field_id": 53})).status_code == 422
    assert (await client.post(path, json={"business_object_field_id": 99999})).status_code == 404
    wrong = f"/sources/{other['id']}/object-field-trackings/{child['id']}"
    for suffix in ("", "/versions", "/versions/1"):
        assert (await client.get(wrong + suffix)).status_code == 404
    assert (
        await client.patch(wrong, json={"expected_version": 1, "tracking_enabled": False})
    ).status_code == 404
    assert (await client.delete(wrong, params={"expected_version": 1})).status_code == 404
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(SourceBusinessObject)) == 1
        assert await session.scalar(select(func.count()).select_from(SourceFieldTracking)) == 1
        assert (
            await session.scalar(select(func.count()).select_from(SourceObjectFieldTracking)) == 1
        )
    second, _ = await track(client, other["id"])
    assert second["id"] != child["id"]
    assert (await client.get("/sources/999/object-field-trackings")).status_code == 404


async def test_changes_append_snapshots_with_contiguous_periods(client, business, sessions):
    source = await register(client)
    first, collection = await track(client, source["id"], desired_refresh_seconds=300)
    path = collection + f"/{first['id']}"
    async with sessions() as session:
        original = (await session.get(SourceObjectFieldTracking, first["version_id"])).model_dump()
    response = await client.patch(
        path,
        json={
            "expected_version": 1,
            "desired_refresh_seconds": 60,
            "change_reason": "Check more often",
        },
    )
    assert response.status_code == 200, response.text
    second = response.json()
    assert second["id"] == first["id"] and second["version_id"] != first["version_id"]
    assert second["version"] == 2 and second["change_reason"] == "Check more often"
    assert (await client.get(collection)).json()["total"] == 1
    old = (await client.get(path + "/versions/1")).json()
    assert old["desired_refresh_seconds"] == 300 and not old["is_current"]
    assert old["valid_to"] == second["valid_from"]
    history = (await client.get(path + "/versions", params={"offset": 1, "limit": 1})).json()
    assert history["total"] == 2 and history["items"][0]["version"] == 2
    async with sessions() as session:
        closed = (await session.get(SourceObjectFieldTracking, first["version_id"])).model_dump()
        assert {k: v for k, v in closed.items() if k != "valid_to"} == {
            k: v for k, v in original.items() if k != "valid_to"
        }
    assert (await client.get(path, params={"at": first["valid_from"]})).json()["version"] == 1
    assert (await client.get(path, params={"at": second["valid_from"]})).json()["version"] == 2
    before = datetime.fromisoformat(first["valid_from"]) - timedelta(microseconds=1)
    assert (await client.get(path, params={"at": before.isoformat()})).status_code == 404
    assert (await client.get(path, params={"at": "2026-01-01T00:00:00"})).status_code == 422
    assert (
        await client.patch(path + "/versions/1", json={"tracking_enabled": False})
    ).status_code == 405
    assert (await client.delete(path + "/versions/1")).status_code == 405


async def test_stale_updates_noops_and_soft_disable(client, business):
    source = await register(client)
    child, collection = await track(client, source["id"], desired_refresh_seconds=60)
    path = collection + f"/{child['id']}"
    response = await client.patch(path, json={"expected_version": 1, "tracking_enabled": True})
    assert response.json()["version_id"] == child["version_id"]
    disabled = await client.delete(path, params={"expected_version": 1})
    assert disabled.status_code == 200 and disabled.json()["version"] == 2
    assert not disabled.json()["tracking_enabled"]
    assert (await client.get(collection, params={"tracking_enabled": True})).json()["total"] == 0
    assert (await client.get(collection)).json()["total"] == 1
    assert (await client.post(collection, json={"business_object_field_id": 50})).status_code == 409
    assert (await client.delete(path, params={"expected_version": 1})).status_code == 409
    assert (await client.delete(path, params={"expected_version": 2})).json()["version"] == 2
    response = await client.patch(
        path,
        json={"expected_version": 2, "tracking_enabled": True, "desired_refresh_seconds": None},
    )
    assert response.status_code == 200 and response.json()["version"] == 3
    assert (
        response.json()["id"] == child["id"] and response.json()["desired_refresh_seconds"] is None
    )
    assert (await client.get(path + "/versions")).json()["total"] == 3


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"tracking_enabled": False},
        {"expected_version": 1},
        {"expected_version": 1, "change_reason": "Only a reason"},
        {"expected_version": 1, "tracking_enabled": None},
        {"expected_version": 1, "desired_refresh_seconds": 0},
        {"expected_version": 1, "business_object_field_id": 51},
        {"expected_version": 1, "source_field_tracking_id": 1},
        {"expected_version": 1, "baseline_observation_id": 123},
        {"expected_version": 1, "last_checked_at": "2026-09-11T12:00:00Z"},
        {"expected_version": 1, "valid_to": "2026-09-11T12:00:00Z"},
    ],
)
async def test_public_tracking_patch_cannot_change_identity_or_worker_fields(
    client, business, payload
):
    source = await register(client)
    child, path = await track(client, source["id"])
    path += f"/{child['id']}"
    assert (await client.patch(path, json=payload)).status_code == 422
    assert (await client.get(path + "/versions")).json()["total"] == 1


async def test_failed_successor_insert_rolls_back_version_close(client, business, sessions):
    source = await register(client)
    child, path = await track(client, source["id"], desired_refresh_seconds=300)
    async with sessions() as session:

        @event.listens_for(session.sync_session, "before_flush")
        def break_successor(db_session, _context, _instances):
            for row in db_session.new:
                if isinstance(row, SourceObjectFieldTracking) and row.version == 2:
                    row.business_object_field_id = None

        service = SourcesService(session)
        with pytest.raises(IntegrityError):
            await service.update_object_field_tracking(
                source["id"],
                UUID(child["id"]),
                SourceObjectFieldTrackingUpdate(expected_version=1, tracking_enabled=False),
            )
        event.remove(session.sync_session, "before_flush", break_successor)
        current = await service.get_object_field_tracking(source["id"], UUID(child["id"]))
        assert current.version == 1 and current.valid_to is None and current.tracking_enabled
        assert (
            await session.scalar(select(func.count()).select_from(SourceObjectFieldTracking)) == 1
        )
        parent = await session.scalar(select(SourceFieldTracking))
        assert parent.tracking_enabled and parent.desired_refresh_seconds == 300
        result = await service.update_object_field_tracking(
            source["id"],
            current.id,
            SourceObjectFieldTrackingUpdate(expected_version=1, tracking_enabled=False),
        )
        assert result.version == 2


async def test_failed_creation_rolls_back_automatically_created_links(client, business, sessions):
    source = await register(client)
    async with sessions() as session:

        @event.listens_for(session.sync_session, "before_flush")
        def break_tracking(db_session, _context, _instances):
            for row in db_session.new:
                if isinstance(row, SourceObjectFieldTracking):
                    row.business_object_field_id = None

        with pytest.raises(IntegrityError):
            await SourcesService(session).create_object_field_tracking(
                source["id"], SourceObjectFieldTrackingCreate(business_object_field_id=50)
            )
        for model in (SourceFieldTracking, SourceBusinessObject, SourceObjectFieldTracking):
            assert await session.scalar(select(func.count()).select_from(model)) == 0


async def test_archive_versions_all_enabled_trackings_and_retains_history(
    client, business, sessions
):
    source = await register(client)
    first, collection = await track(client, source["id"])
    second, _ = await track(client, source["id"], 52)
    disabled, _ = await track(client, source["id"], 51, tracking_enabled=False)
    source_path = f"/sources/{source['id']}"
    await client.put(source_path + "/check-schedule", json={"interval_seconds": 300})
    for _ in range(2):
        assert (await client.delete(source_path)).status_code == 204
    assert not (await client.get(source_path + "/check-schedule")).json()["enabled"]
    for child in (first, second):
        path = collection + f"/{child['id']}"
        current = (await client.get(path)).json()
        assert current["version"] == 2 and not current["tracking_enabled"]
        old = (await client.get(path + "/versions/1")).json()
        assert old["tracking_enabled"] and old["valid_to"] == current["valid_from"]
        assert (
            await client.patch(path, json={"expected_version": 2, "tracking_enabled": True})
        ).status_code == 409
    assert (await client.get(collection + f"/{disabled['id']}")).json()["version"] == 1
    async with sessions() as session:
        parents = list(await session.scalars(select(SourceFieldTracking)))
        assert all(not row.tracking_enabled for row in parents)
        assert await session.scalar(select(func.count()).select_from(SourceBusinessObject)) == 2
        assert (
            await session.scalar(select(func.count()).select_from(SourceObjectFieldTracking)) == 5
        )


async def test_internal_observation_check_is_versioned_and_requires_existing_evidence(
    client, business, sessions
):
    source = await register(client)
    child, path = await track(client, source["id"])
    async with sessions() as session:
        service = SourcesService(session)
        checked = await service.record_tracking_observation(
            source["id"],
            UUID(child["id"]),
            TrackingObservationUpdate(expected_version=1, last_checked_at=datetime.now(UTC)),
        )
        assert checked.version == 2 and checked.last_changed_at is None
        assert checked.baseline_observation_id is None
        with pytest.raises(SourceValidationError, match="Observation"):
            await service.record_tracking_observation(
                source["id"],
                checked.id,
                TrackingObservationUpdate(expected_version=2, baseline_observation_id=123),
            )
        assert (await service.get_object_field_tracking(source["id"], checked.id)).version == 2
        await service.update_object_field_tracking(
            source["id"],
            checked.id,
            SourceObjectFieldTrackingUpdate(expected_version=2, tracking_enabled=False),
        )
        with pytest.raises(SourceConflict, match="disabled"):
            await service.record_tracking_observation(
                source["id"],
                checked.id,
                TrackingObservationUpdate(expected_version=3, last_checked_at=datetime.now(UTC)),
            )


async def test_evidence_can_reference_older_versions_of_the_same_binding(
    client, business, sessions
):
    source = await register(client)
    child, collection = await track(client, source["id"])
    other, _ = await track(client, source["id"], 51)
    async with sessions() as session:
        run = ExtractionRun(source_id=source["id"], source_snapshot_id=100, status="completed")
        session.add(run)
        await session.flush()
        parent_id = (
            await session.get(SourceObjectFieldTracking, child["version_id"])
        ).source_field_tracking_id
        other_parent = (
            await session.get(SourceObjectFieldTracking, other["version_id"])
        ).source_field_tracking_id
        first_slot = await session.get(BusinessObjectField, 50)
        other_slot = await session.get(BusinessObjectField, 51)
        session.add_all(
            [
                FieldObservation(
                    id=100,
                    extraction_run_id=run.id,
                    source_field_tracking_id=parent_id,
                    source_object_field_tracking_id=child["version_id"],
                    business_object_id=first_slot.business_object_id,
                    business_object_field_id=50,
                ),
                FieldObservation(
                    id=101,
                    extraction_run_id=run.id,
                    source_field_tracking_id=other_parent,
                    source_object_field_tracking_id=other["version_id"],
                    business_object_id=other_slot.business_object_id,
                    business_object_field_id=51,
                ),
            ]
        )
        await session.commit()
        service = SourcesService(session)
        for bad_id in (101, 999):
            with pytest.raises(SourceValidationError):
                await service.record_tracking_observation(
                    source["id"],
                    UUID(child["id"]),
                    TrackingObservationUpdate(expected_version=1, baseline_observation_id=bad_id),
                )
        v2 = await service.record_tracking_observation(
            source["id"],
            UUID(child["id"]),
            TrackingObservationUpdate(
                expected_version=1, baseline_observation_id=100, last_observation_id=100
            ),
        )
        v3 = await service.update_object_field_tracking(
            source["id"],
            v2.id,
            SourceObjectFieldTrackingUpdate(expected_version=2, desired_refresh_seconds=60),
        )
        v4 = await service.record_tracking_observation(
            source["id"],
            v3.id,
            TrackingObservationUpdate(
                expected_version=3, baseline_observation_id=100, last_checked_at=datetime.now(UTC)
            ),
        )
        assert v4.version == 4 and v4.baseline_observation_id == 100
        assert v4.last_changed_at is None
        assert (await session.get(FieldObservation, 100)).source_object_field_tracking_id == child[
            "version_id"
        ]
    first = (await client.get(collection + f"/{child['id']}/versions/1")).json()
    assert first["last_observation_id"] is None and first["baseline_observation_id"] is None


@pytest.mark.skipif(not os.environ.get("SOURCES_TEST_DATABASE_URL"), reason="Requires PostgreSQL")
async def test_concurrent_tracking_creation_and_version_rollover(client, business, sessions):
    source = await register(client)

    async def create():
        async with sessions() as session:
            return await SourcesService(session).create_object_field_tracking(
                source["id"], SourceObjectFieldTrackingCreate(business_object_field_id=50)
            )

    results = await asyncio.gather(create(), create(), return_exceptions=True)
    assert sum(isinstance(result, SourceConflict) for result in results) == 1
    child = next(result for result in results if not isinstance(result, Exception))

    async def change(interval):
        async with sessions() as session:
            return await SourcesService(session).update_object_field_tracking(
                source["id"],
                child.id,
                SourceObjectFieldTrackingUpdate(
                    expected_version=1, desired_refresh_seconds=interval
                ),
            )

    results = await asyncio.gather(change(60), change(300), return_exceptions=True)
    assert sum(isinstance(result, SourceConflict) for result in results) == 1
    assert sum(not isinstance(result, Exception) for result in results) == 1
    async with sessions() as session:
        versions = list(
            await session.scalars(
                select(SourceObjectFieldTracking).order_by(SourceObjectFieldTracking.version)
            )
        )
        assert len(versions) == 2 and versions[0].valid_to == versions[1].valid_from
        assert versions[1].valid_to is None
        assert await session.scalar(select(func.count()).select_from(SourceFieldTracking)) == 1
        assert await session.scalar(select(func.count()).select_from(SourceBusinessObject)) == 1
