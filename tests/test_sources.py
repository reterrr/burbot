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

from shared.database import get_session  # noqa: E402
from sources.api.routes import router  # noqa: E402
from sources.exceptions import SourceConflict  # noqa: E402
from sources.schemas.api import SourceCreateRequest, SourceStateChangeRequest  # noqa: E402
from sources.schemas.common import utc_now  # noqa: E402
from sources.schemas.models import Source, SourceStateHistory, StoredFile  # noqa: E402
from sources.services.repositories import SourceRepository  # noqa: E402
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
                    tables=[StoredFile.__table__, Source.__table__, SourceStateHistory.__table__],
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


async def register(client, url="https://example.com/page", source_type="HTML", **extra):
    response = await client.post("/sources", json={"url": url, "source_type": source_type, **extra})
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
        await service.create_source(
            SourceCreateRequest(url="https://example.com", source_type="HTML")
        )
        with pytest.raises(SourceConflict):
            await service.create_source(
                SourceCreateRequest(
                    url="https://EXAMPLE.com:443/#other",
                    source_type="PDF",
                )
            )
        await service.create_source(
            SourceCreateRequest(url="https://example.org", source_type="HTML")
        )
        assert await session.scalar(select(func.count()).select_from(Source)) == 2
        assert await session.scalar(select(func.count()).select_from(SourceStateHistory)) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"url": "file:///etc/passwd", "source_type": "HTML"},
        {"url": "https://user:password@example.com", "source_type": "HTML"},
        {"url": "https://example.com", "source_type": "CSV"},
        {"url": "https://example.com", "source_type": "HTML", "state": "ACTIVE"},
        {"url": "https://example.com", "source_type": "HTML", "file_id": 0},
        {"url": "https://example.com/" + "a" * 2049, "source_type": "HTML"},
    ],
)
async def test_invalid_registration_returns_422_without_writes(client, payload):
    assert (await client.post("/sources", json=payload)).status_code == 422
    assert (await client.get("/sources")).json()["total"] == 0


async def test_listing_filters_counts_and_pagination(client):
    first = await register(client)
    second = await register(client, "https://example.com/second")
    await register(client, "https://example.com/document.pdf", "PDF")
    response = await client.get("/sources", params={"source_type": "HTML", "offset": 1, "limit": 1})
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert [item["id"] for item in response.json()["items"]] == [second["id"]]
    response = await client.get("/sources", params={"url": "HTTPS://EXAMPLE.COM:443/page#section"})
    assert [item["id"] for item in response.json()["items"]] == [first["id"]]
    assert (await client.get("/sources", params={"state": "ACTIVE"})).json()["total"] == 0
    for params in ({"offset": -1}, {"limit": 0}, {"limit": 101}, {"state": "INVALID"}):
        assert (await client.get("/sources", params=params)).status_code == 422


async def test_file_reference_validation(client, sessions):
    async with sessions() as session:
        pdf = StoredFile(storage_key="test/pdf", mime_type="application/pdf")
        purged = StoredFile(
            storage_key="test/purged", mime_type="application/pdf", purged_at=utc_now()
        )
        session.add_all([pdf, purged])
        await session.commit()
        pdf_id, purged_id = pdf.id, purged.id
    for file_id, kind in ((999999, "PDF"), (purged_id, "PDF"), (pdf_id, "HTML")):
        response = await client.post(
            "/sources",
            json={
                "url": "https://example.com/file",
                "source_type": kind,
                "file_id": file_id,
            },
        )
        assert response.status_code == 422
    source = await register(client, "https://example.com/file", "PDF", file_id=pdf_id)
    assert source["file_id"] == pdf_id
    response = await client.patch(f"/sources/{source['id']}", json={"file_id": None})
    assert response.status_code == 200
    assert response.json()["file_id"] is None


async def test_updates_detect_conflicts_and_preserve_existing_data(client):
    first = await register(client)
    second = await register(client, "https://example.com/second")
    path = f"/sources/{second['id']}"
    response = await client.patch(path, json={"url": first["url"]})
    assert response.status_code == 409
    assert (await client.get(path)).json()["url"] == second["url"]
    for payload in ({}, {"url": None}, {"source_type": None}, {"state": "ACTIVE"}):
        assert (await client.patch(path, json=payload)).status_code == 422
    response = await client.patch(
        path, json={"url": "https://example.org/new", "source_type": "PDF"}
    )
    assert response.status_code == 200
    assert response.json()["source_type"] == "PDF"
    assert (
        await client.put(
            path + "/state",
            json={
                "expected_state": "UNDISCOVERED",
                "state": "DISCOVERING",
            },
        )
    ).status_code == 200
    assert (await client.patch(path, json={"source_type": "HTML"})).status_code == 409


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
        await client.patch("/sources/999", json={"source_type": "PDF"}),
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
    class BrokenHistoryRepository(SourceRepository):
        def add_history(self, entry):
            entry.to_state = None  # Force a database failure when the transaction commits.
            super().add_history(entry)

    async with sessions() as session:
        broken = SourcesService(session, BrokenHistoryRepository(session))
        request = SourceCreateRequest(url="https://example.com", source_type="HTML")
        with pytest.raises(IntegrityError):
            await broken.create_source(request)
        assert await session.scalar(select(func.count()).select_from(Source)) == 0
        source = await SourcesService(session).create_source(request)
        with pytest.raises(IntegrityError):
            await broken.change_state(
                source.id,
                SourceStateChangeRequest(
                    state="DISCOVERING",
                    expected_state="UNDISCOVERED",
                ),
            )
        assert (await SourcesService(session).get_source(source.id)).state == "UNDISCOVERED"
        assert await session.scalar(select(func.count()).select_from(SourceStateHistory)) == 1


@pytest.mark.skipif(not os.environ.get("SOURCES_TEST_DATABASE_URL"), reason="Requires PostgreSQL")
async def test_concurrent_registration_and_transitions(sessions):
    async def register_source():
        async with sessions() as session:
            return await SourcesService(session).create_source(
                SourceCreateRequest(
                    url="https://example.com",
                    source_type="HTML",
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
