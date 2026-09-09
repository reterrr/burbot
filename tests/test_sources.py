"""API and transaction checks; optionally run against a dedicated PostgreSQL test DB."""

import asyncio
import os
from uuid import uuid4

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
from sources.exceptions import SourceConflict  # noqa: E402
from sources.schemas.api import SourceCreateRequest, SourceStateChangeRequest  # noqa: E402
from sources.schemas.models import (  # noqa: E402
    SOURCE_TABLES,
    Source,
    SourceStateHistory,
)


@compiles(BigInteger, "sqlite")
def sqlite_bigint(_type, _compiler, **_kwargs):
    return "INTEGER"


@compiles(JSONB, "sqlite")
def sqlite_jsonb(_type, _compiler, **_kwargs):
    return "JSON"


from sources.services.sources import SourcesService  # noqa: E402

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


async def track(client, source_id, field_id=30, object_field_id=50):
    path = f"/sources/{source_id}/field-trackings"
    response = await client.post(path, json={"business_entity_field_id": field_id})
    assert response.status_code == 201, response.text
    parent = response.json()
    path += f"/{parent['id']}/object-field-trackings"
    response = await client.post(path, json={"business_object_field_id": object_field_id})
    assert response.status_code == 201, response.text
    return parent, response.json(), path


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
        path + "/field-trackings",
        json={
            "business_entity_field_id": 31,
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


async def test_business_links_are_validated_context_only(client, business):
    source = await register(client)
    path = f"/sources/{source['id']}"
    assert (await client.put(path + "/business-entities/99999")).status_code == 404
    assert (await client.put(path + "/business-objects/99999")).status_code == 404
    for _ in range(2):
        assert (await client.put(path + "/business-entities/20")).status_code == 200
        assert (await client.put(path + "/business-objects/40")).status_code == 200
    assert (await client.get(path + "/business-entities")).json()["total"] == 1
    assert (await client.get(path + "/business-objects")).json()["total"] == 1
    assert (await client.get(path + "/field-trackings")).json()["total"] == 0
    for _ in range(2):
        assert (await client.delete(path + "/business-entities/20")).status_code == 204
        assert (await client.delete(path + "/business-objects/40")).status_code == 204
    assert (await client.get(path + "/business-entities")).json()["total"] == 0


async def test_object_tracking_requires_matching_entity_field_and_source(client, business):
    source = await register(client)
    other = await register(client, "https://example.org")
    parent, child, path = await track(client, source["id"])
    assert (await client.post(path, json={"business_object_field_id": 50})).status_code == 409
    for slot in (52, 53):
        assert (await client.post(path, json={"business_object_field_id": slot})).status_code == 422
    assert (await client.post(path, json={"business_object_field_id": 99999})).status_code == 404
    assert (
        await client.post(
            f"/sources/{source['id']}/field-trackings", json={"business_entity_field_id": 30}
        )
    ).status_code == 409
    wrong_parent = path.replace(f"/sources/{source['id']}", f"/sources/{other['id']}")
    assert (await client.get(wrong_parent)).status_code == 404
    assert (
        await client.patch(wrong_parent + f"/{child['id']}", json={"tracking_enabled": False})
    ).status_code == 404
    response = await client.patch(
        f"/sources/{source['id']}/field-trackings/{parent['id']}",
        json={
            "desired_refresh_seconds": 60,
        },
    )
    assert response.status_code == 200
    response = await client.patch(
        f"/sources/{source['id']}/field-trackings/{parent['id']}",
        json={
            "desired_refresh_seconds": None,
        },
    )
    assert response.json()["desired_refresh_seconds"] is None
    assert (
        await client.patch(path + f"/{child['id']}", json={"tracking_enabled": None})
    ).status_code == 422


async def test_tracking_timestamps_and_pending_evidence_layer(client, business):
    source = await register(client)
    _parent, child, path = await track(client, source["id"])
    path += f"/{child['id']}"
    response = await client.patch(path, json={"last_checked_at": "2026-09-09T12:00:00Z"})
    assert response.status_code == 200
    assert response.json()["last_changed_at"] is None
    assert response.json()["baseline_observation_id"] is None
    response = await client.patch(path, json={"baseline_observation_id": 123})
    assert response.status_code == 409 and "Layer 3" in response.json()["detail"]
    assert (await client.get(path)).json()["baseline_observation_id"] is None


async def test_archive_disables_cadence_and_tracking(client, business):
    source = await register(client)
    _parent, child, child_path = await track(client, source["id"])
    path = f"/sources/{source['id']}"
    await client.put(path + "/check-schedule", json={"interval_seconds": 300})
    response = await client.put(
        path + "/state", json={"state": "ARCHIVED", "expected_state": "UNDISCOVERED"}
    )
    assert response.status_code == 200
    assert not (await client.get(path + "/check-schedule")).json()["enabled"]
    assert not (await client.get(path + "/field-trackings")).json()["items"][0]["tracking_enabled"]
    assert not (await client.get(child_path + f"/{child['id']}")).json()["tracking_enabled"]
    assert (
        await client.patch(child_path + f"/{child['id']}", json={"tracking_enabled": True})
    ).status_code == 409
    assert (
        await client.put(path + "/check-schedule", json={"interval_seconds": 300})
    ).status_code == 409


async def test_observations_must_belong_to_the_exact_binding(client, business, sessions):
    from sqlalchemy import Column, Table

    source = await register(client)
    parent, child, path = await track(client, source["id"])
    other_child = (await client.post(path, json={"business_object_field_id": 51})).json()
    path += f"/{child['id']}"
    # A test-only projection of Layer 3's reference contract, not a production model.
    observations = Table(
        "field_observations",
        SQLModel.metadata,
        Column("id", BigInteger, primary_key=True),
        Column("source_field_tracking_id", BigInteger, nullable=False),
        Column("source_object_field_tracking_id", BigInteger, nullable=True),
    )
    try:
        async with sessions() as session:
            connection = await session.connection()
            await connection.run_sync(observations.create)
            await session.execute(
                observations.insert(),
                [
                    {
                        "id": 100,
                        "source_field_tracking_id": parent["id"],
                        "source_object_field_tracking_id": child["id"],
                    },
                    {
                        "id": 101,
                        "source_field_tracking_id": parent["id"],
                        "source_object_field_tracking_id": other_child["id"],
                    },
                    {
                        "id": 102,
                        "source_field_tracking_id": parent["id"] + 999,
                        "source_object_field_tracking_id": child["id"],
                    },
                ],
            )
            await session.commit()
        for bad_id in (101, 102, 999):
            assert (
                await client.patch(path, json={"baseline_observation_id": bad_id})
            ).status_code == 422
        response = await client.patch(
            path, json={"last_observation_id": 100, "baseline_observation_id": 100}
        )
        assert response.status_code == 200
        assert response.json()["baseline_observation_id"] == 100
        assert response.json()["last_changed_at"] is None
        response = await client.patch(path, json={"last_checked_at": "2026-09-09T12:00:00Z"})
        assert response.json()["baseline_observation_id"] == 100
        assert response.json()["last_changed_at"] is None
    finally:
        SQLModel.metadata.remove(observations)
