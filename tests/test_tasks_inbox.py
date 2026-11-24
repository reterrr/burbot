from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from test_collections_postgres import database as database

from tasks.api.database import get_session
from tasks.api.routes import router
from tasks.schemas.models import Task, Workflow

pytestmark = pytest.mark.asyncio


async def test_inbox_filters_count_and_workflow_status_actions(database):
    _, factory, _ = database
    async with factory.begin() as session:
        active = Workflow(source_id=10, source_snapshot_id=100)
        historical = Workflow(source_id=10, source_snapshot_id=99, status="superseded")
        other_source = Workflow(source_id=11, source_snapshot_id=101)
        session.add_all([historical, active, other_source])
        await session.flush()
        active.previous_workflow_id = historical.id
        same_time = datetime(2026, 11, 24, tzinfo=UTC)
        common = dict(type="review_source_change", reason="value_changed", created_at=same_time)
        pending = Task(workflow_id=active.id, status="pending", **common)
        working = Task(workflow_id=active.id, status="in_progress", **common)
        failed = Task(workflow_id=active.id, status="failed", **common)
        superseded = Task(workflow_id=historical.id, status="cancelled", **common)
        other = Task(workflow_id=other_source.id, type="discover_source", reason="manual")
        session.add_all([pending, working, failed, superseded, other])

    app = FastAPI()
    app.include_router(router)

    async def sessions():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/tasks/inbox")
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 3
        assert (await client.get("/tasks/inbox/count")).json() == 3

        filters = {"source_id": 10, "type": "review_source_change", "reason": "value_changed"}
        page = (
            await client.get("/tasks/inbox", params={**filters, "offset": 1, "limit": 1})
        ).json()
        assert (page["total"], page["offset"], page["limit"]) == (2, 1, 1)
        assert page["applied_filters"] == filters
        assert page["items"][0]["task"]["id"] == pending.id
        assert "in_progress" in page["items"][0]["allowed_statuses"]

        filtered = await client.get(
            "/tasks/inbox", params={**filters, "status": "in_progress", "task_id": working.id}
        )
        assert filtered.status_code == 200, filtered.text
        assert filtered.json()["total"] == 1
        assert filtered.json()["items"][0]["task"]["id"] == working.id
        assert (await client.get("/tasks/inbox", params={"task_id": superseded.id})).json()[
            "total"
        ] == 0
        assert (await client.get("/tasks/inbox", params={"status": "FAILED"})).status_code == 422

        failed_detail = (await client.get(f"/tasks/{failed.id}")).json()
        assert failed_detail["allowed_statuses"] == ["cancelled", "in_progress", "pending"]
        patch = await client.patch(f"/tasks/{failed.id}/status", json={"status": "pending"})
        assert patch.status_code == 200, patch.text
        assert patch.json()["status"] == "pending"
        assert (await client.get("/tasks/inbox/count")).json() == 4

        history = (await client.get("/tasks/sources/10/workflows")).json()["items"]
        assert {row["status"] for row in history} == {"active", "superseded"}
        historical_tasks = (await client.get(f"/tasks/workflows/{historical.id}/tasks")).json()
        assert historical_tasks["items"][0]["id"] == superseded.id
        assert (await client.get(f"/tasks/{superseded.id}")).json()["allowed_statuses"] == []
        stale = await client.patch(f"/tasks/{superseded.id}/status", json={"status": "in_progress"})
        assert stale.status_code == 409
