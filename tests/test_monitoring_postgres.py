"""Drive the same REST protocol as Firefox against PostgreSQL and real MinIO."""

import asyncio
import os
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from test_collections_postgres import database as database
from test_collections_postgres import domain as domain
from test_selector_tree import css, part, recipe, tree

from business_layer.schemas.models import BusinessObject, BusinessObjectFieldValue
from extraction.schemas.common import utc_now
from extraction.schemas.models import ConcreteValue, FieldObservation
from extraction.schemas.selector import SelectorEvaluation
from extraction.schemas.selector_tree import SelectorVersionDefinition
from extraction.services.selector_resolver import HtmlSelectorRuntime, evaluate_selector_version
from monitoring.models import MonitoringJob, MonitoringUpload
from monitoring.processing import MonitoringProcessor
from monitoring.queue import MonitoringQueue
from monitoring.security import MonitoringError, origin
from sources.schemas.models import (
    Source,
    SourceCheckSchedule,
    SourceObjectFieldTracking,
    SourceSnapshot,
    StoredFile,
)
from tasks.schemas.models import Task, TaskStatus, Workflow

pytestmark = pytest.mark.asyncio
PAGE = "https://example.org/projects"
OPERATOR = {"Authorization": "Bearer monitoring-test-operator"}


@pytest_asyncio.fixture
async def minio(monkeypatch):
    endpoint = os.getenv("MONITORING_TEST_S3_URL")
    if not endpoint:
        pytest.skip("Set MONITORING_TEST_S3_URL for real MinIO tests")
    name = "monitoring-test-" + uuid4().hex
    params = {
        "INTERNAL_URL": endpoint,
        "PUBLIC_URL": endpoint,
        "BUCKET": name,
        "ACCESS_KEY": os.environ["MONITORING_TEST_S3_ACCESS_KEY"],
        "SECRET_KEY": os.environ["MONITORING_TEST_S3_SECRET_KEY"],
    }
    for key, value in params.items():
        monkeypatch.setenv("MONITORING_S3_" + key, value)
    from monitoring.storage import storage_from_env

    storage_from_env.cache_clear()
    store = storage_from_env()
    store.reader.create_bucket(Bucket=name)
    try:
        yield store
    finally:
        storage_from_env.cache_clear()
        for obj in store.reader.list_objects_v2(Bucket=name).get("Contents", []):
            store.reader.delete_object(Bucket=name, Key=obj["Key"])
        store.reader.delete_bucket(Bucket=name)


@pytest_asyncio.fixture
async def client(domain, monkeypatch):
    monkeypatch.setenv("MONITORING_ADMIN_TOKEN", OPERATOR["Authorization"].split()[1])
    monkeypatch.setenv("DCKR_DATABASE_URL", os.environ["COLLECTIONS_TEST_DATABASE_URL"])
    from extraction.api.routes import capture_router
    from monitoring.api import router
    from shared.database import get_session

    app = FastAPI()
    app.include_router(router)
    app.include_router(capture_router)

    async def sessions():
        async with domain.factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as api:
        yield api


async def source(domain, client, *, enabled=True, state="ACTIVE"):
    async with domain.factory.begin() as session:
        row = Source(type="HTML", url=f"{PAGE}/{uuid4()}", state=state)
        session.add(row)
        await session.flush()
        session.add(SourceCheckSchedule(source_id=row.id, enabled=enabled, interval_seconds=60))
    response = await client.put(f"/monitoring/sources/{row.id}/approval", json={}, headers=OPERATOR)
    assert response.status_code == 200, response.text
    return row


async def agent(client, *source_ids):
    response = await client.post(
        "/monitoring/agents/register",
        headers=OPERATOR,
        json={"name": "Test agent", "sourceIds": source_ids},
    )
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    return {"Authorization": "Bearer " + data["agentToken"]}, data["agentId"]


async def enqueue(client, source_id):
    response = await client.post(f"/monitoring/sources/{source_id}/jobs", headers=OPERATOR)
    assert response.status_code == 200, response.text
    return response.json()["jobId"]


async def claim(client, headers):
    response = await client.post("/monitoring/jobs/claim", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def history(client, source_id):
    response = await client.get(f"/monitoring/sources/{source_id}/history", headers=OPERATOR)
    assert response.status_code == 200, response.text
    return response.json()


def operation(job, action):
    return f"/monitoring/jobs/{job['jobId']}/{action}"


async def test_scheduler_concurrency_access_and_expired_lease(domain, client):
    due = await source(domain, client)
    disabled = await source(domain, client, enabled=False)
    await source(domain, client, state="UNDISCOVERED")
    first, first_id = await agent(client, due.id)
    second, _ = await agent(client, due.id)
    other, _ = await agent(client, disabled.id)

    async def schedule():
        async with domain.factory.begin() as session:
            return await MonitoringQueue(session).schedule_due("scheduler-run")

    planned = [job for batch in await asyncio.gather(schedule(), schedule()) for job in batch]
    assert [job.source_id for job in planned] == [due.id]
    assert await enqueue(client, due.id) == str(planned[0].id)
    assert (await history(client, due.id))[0]["status"] == "pending"
    base = "/monitoring/jobs"
    assert (await client.post(base + "/claim", headers=other)).status_code == 204
    assert (await client.post(base + "/claim")).status_code == 401
    assert (await client.post("/monitoring/agents/heartbeat", headers=first)).status_code == 200
    assert (await client.get(f"/monitoring/agents/{first_id}", headers=OPERATOR)).json()[
        "connected"
    ]
    claims = await asyncio.gather(
        *(client.post(base + "/claim", headers=h) for h in (first, second))
    )
    assert sorted(r.status_code for r in claims) == [200, 204]
    winner, loser = (first, second) if claims[0].status_code == 200 else (second, first)
    job = next(r.json() for r in claims if r.status_code == 200)
    assert job["representation"] == "rendered_dom"
    assert (await client.get(base + "/" + job["jobId"], headers=loser)).status_code == 404
    heartbeat = {"leaseId": job["leaseId"], "phase": "capturing"}
    assert (await client.post(operation(job, "heartbeat"), headers=winner, json=heartbeat)).json()[
        "status"
    ] == "capturing"
    async with domain.factory.begin() as session:
        row = await session.get(MonitoringJob, planned[0].id)
        row.lease_expires_at = utc_now() - timedelta(seconds=1)
        assert await MonitoringQueue(session).expire_leases() == 0
        await session.flush()
        assert await MonitoringQueue(session).expire_leases() == 1
        row.available_at = utc_now()
    assert (
        await client.post(
            operation(job, "heartbeat"),
            headers=winner,
            json=heartbeat,
        )
    ).status_code == 409
    reissued = await claim(client, loser)
    assert reissued["jobId"] == job["jobId"] and reissued["leaseId"] != job["leaseId"]
    revoke = (await client.post("/monitoring/agents/heartbeat", headers=loser)).json()["agentId"]
    await client.delete(f"/monitoring/agents/{revoke}", headers=OPERATOR)
    assert (await client.post(base + "/claim", headers=loser)).status_code == 401
    assert (await history(client, due.id))[0]["status"] == "retry_pending"
    async with domain.factory() as session:
        schedule_row = await session.get(SourceCheckSchedule, due.id)
        assert schedule_row.last_checked_at is None and schedule_row.next_check_at is None
        assert (
            await session.scalar(
                select(MonitoringJob).where(MonitoringJob.source_id == disabled.id)
            )
            is None
        )


async def prepare(client, headers, job, html, structure, *, digest=None):
    upload = {
        "leaseId": job["leaseId"],
        "representation": "rendered_dom",
        "mimeType": "text/html",
        "contentSize": len(html),
        "contentHash": digest if digest else sha256(html).hexdigest(),
    }
    res = await client.post(operation(job, "uploads"), json=upload, headers=headers)
    assert res.status_code == 200, res.text
    grant = res.json()
    report = []
    for pin in job["selectors"]:
        definition = SelectorVersionDefinition.model_validate(pin["definition"])
        result = evaluate_selector_version(definition, HtmlSelectorRuntime(html, job["url"]))
        report.append(
            {"definitionFingerprint": pin["definitionFingerprint"], "result": result.portable()}
        )
    return grant, {
        **upload,
        "uploadIntentId": grant["uploadIntentId"],
        "completionKey": str(uuid4()),
        "representationVersion": "firefox-dom-1",
        "structureHashVersion": "dom-shape-1",
        "hashAlgorithm": "sha256",
        "structureHash": structure,
        "pageUrl": job["url"],
        "capturedAt": utc_now().isoformat(),
        "evaluations": report,
    }


async def put(grant, html, *, expected=200):
    async with AsyncClient() as wire:
        res = await wire.put(grant["url"], content=html, headers={"Content-Type": "text/html"})
        assert res.status_code == expected, res.text


async def complete(client, headers, job, data, expected=200):
    res = await client.post(operation(job, "complete"), json=data, headers=headers)
    assert res.status_code == expected, res.text
    return res.json()


async def process(domain, job, *, retry=False):
    identity = UUID(job["jobId"])
    async with domain.factory.begin() as session:
        assert await MonitoringProcessor(session).acquire(identity, "prefect-processing-run")
    if retry:
        async with domain.factory.begin() as session:
            await MonitoringProcessor(session).retry_processing(identity, "failed-run")
        async with domain.factory.begin() as session:
            row = await session.get(MonitoringJob, identity)
            assert row.processing_attempts == 1 and row.error_code == "PROCESSING_FAILED"
            row.available_at = utc_now()
        async with domain.factory.begin() as session:
            assert await MonitoringProcessor(session).acquire(identity, "retry-run")
    async with domain.factory.begin() as session:
        assert await MonitoringProcessor(session).process(identity)
    async with domain.factory.begin() as session:
        assert not await MonitoringProcessor(session).acquire(identity)


async def monitor(client, domain, headers, source_id, html, structure="a" * 64):
    await enqueue(client, source_id)
    job = await claim(client, headers)
    grant, data = await prepare(client, headers, job, html, structure)
    await put(grant, html)
    await complete(client, headers, job, data)
    await process(domain, job)
    return (await history(client, source_id))[0]


async def test_verified_upload_replay_cleanup_and_snapshot_compatibility(domain, client, minio):
    row = await source(domain, client)
    headers, _ = await agent(client, row.id)
    await enqueue(client, row.id)
    job = await claim(client, headers)
    html = b"<p>First</p>"
    grant, data = await prepare(client, headers, job, html, "a" * 64)
    assert (await complete(client, headers, job, data, 409))["detail"]["code"] == "UPLOAD_NOT_FOUND"
    # MinIO checks the signed length and allows only one bounded body length.
    await put(grant, html + b"!", expected=403)
    await put(grant, b"!" * len(html))
    assert (await complete(client, headers, job, data, 422))["detail"][
        "code"
    ] == "UPLOAD_HASH_MISMATCH"
    await put(grant, html)
    assert (await complete(client, headers, job, data))["status"] == "uploaded"
    assert (await complete(client, headers, job, data))["status"] == "uploaded"
    assert (await complete(client, headers, job, {**data, "completionKey": str(uuid4())}, 409))[
        "detail"
    ]["code"] == "COMPLETION_CONFLICT"
    await put(grant, b"!" * len(html))
    await process(domain, job, retry=True)
    result = await complete(client, headers, job, data)
    assert result["status"] == "completed"
    async with domain.factory.begin() as session:
        intent = await session.get(MonitoringUpload, UUID(grant["uploadIntentId"]))
        stored = await session.scalar(
            select(StoredFile).where(StoredFile.storage_key == intent.sealed_key)
        )
        with minio.reader.get_object(Bucket=minio.bucket, Key=stored.storage_key)["Body"] as body:
            assert body.read() == html
        intent.expires_at = utc_now() - timedelta(seconds=1)
        await session.flush()
        assert await MonitoringQueue(session).cleanup_uploads() == 1
        assert [
            x["Key"] for x in minio.reader.list_objects_v2(Bucket=minio.bucket)["Contents"]
        ] == [intent.sealed_key]
    checks = await history(client, row.id)
    assert checks[0]["changeStatus"] == "INITIAL_FETCH"
    assert checks[0]["processingFlowRunId"] == "retry-run"
    assert (await monitor(client, domain, headers, row.id, html))["changeStatus"] == "UNCHANGED"
    assert await domain.count(SourceSnapshot, source_id=row.id) == 1
    assert (await monitor(client, domain, headers, row.id, b"<p>Second</p>"))[
        "changeStatus"
    ] == "CONTENT_CHANGED"
    assert (await monitor(client, domain, headers, row.id, b"<p>Second</p>", "b" * 64))[
        "changeStatus"
    ] == "STRUCTURE_CHANGED"
    async with domain.factory.begin() as session:
        prior = await session.scalar(
            select(SourceSnapshot).order_by(SourceSnapshot.id.desc()).limit(1)
        )
        prior.representation_version = "other-version"
    assert (await monitor(client, domain, headers, row.id, html))["changeStatus"] == "INITIAL_FETCH"


async def add_tree(client, domain, source_id, slot, definition, etag=None):
    response = await client.post(
        "/extraction/selectors/import",
        headers={"If-Match": etag} if etag else {},
        json={
            "tree": definition,
            "binding": {
                "sourceId": source_id,
                "businessEntityFieldId": domain.fields["name"],
                **({"businessObjectFieldId": slot.object_field_id} if slot else {}),
            },
        },
    )
    assert response.status_code == 200, response.text
    return response.headers["etag"]


async def test_detected_evidence_baseline_version_pins_and_review_carry(domain, client, minio):
    row = await source(domain, client)
    obj = await domain.make(name="Canonical")
    slot = domain.slot(obj, "name")
    initial = tree(recipe(part(css("#name"))))
    etag = await add_tree(client, domain, row.id, slot, initial)
    headers, _ = await agent(client, row.id)
    content = b'<p id="name">Baseline</p>'
    first = await monitor(client, domain, headers, row.id, content)
    old_observation_id = first["fields"][0]["observationId"]
    assert first["fields"][0]["status"] == "FIELD_NEW"

    # A human acceptance is represented by advancing the existing evidence
    # tracking baseline, through the same tracking service used by capture.
    from extraction.services.repositories import ExtractionRepository

    async with domain.factory.begin() as session:
        repo = ExtractionRepository(session)
        obs = await repo.get(FieldObservation, old_observation_id)
        assert obs.status == "DETECTED"
        row_tracking = await repo.current_tracking(
            obs.source_field_tracking_id, obs.business_object_field_id
        )
        assert row_tracking.baseline_observation_id is None
        obs.status = "ACCEPTED"
        from sources.services.tracking import append_tracking_version

        await append_tracking_version(
            session,
            row_tracking,
            changes={"baseline_observation_id": obs.id},
            reason="test acceptance",
        )

    unchanged = await monitor(client, domain, headers, row.id, content)
    assert unchanged["fields"][0]["status"] == "FIELD_UNCHANGED"
    assert unchanged["fields"][0]["taskId"] is None
    assert unchanged["sourceSnapshotId"] == first["sourceSnapshotId"]

    await enqueue(client, row.id)
    pinned = await claim(client, headers)
    version = initial["versions"][0]
    path = f"/extraction/selectors/{initial['selector']['uuid']}/drafts"
    drafted = await client.post(path, headers={"If-Match": etag})
    assert drafted.status_code == 200, drafted.text
    next_version = drafted.json()["versions"][-1]
    next_version["recipes"][0]["parts"][0]["locators"][0]["selector"] = "#alternate"
    draft_path = f"{path}/{next_version['uuid']}"
    saved = await client.put(
        draft_path, json=next_version, headers={"If-Match": drafted.headers["etag"]}
    )
    assert saved.status_code == 200, saved.text
    approved = await client.post(
        draft_path + "/approve",
        headers={"If-Match": saved.headers["etag"]},
    )
    assert approved.status_code == 200, approved.text

    html = b'<p id="name">New</p><p id="alternate">New</p>'
    grant, payload = await prepare(client, headers, pinned, html, "b" * 64)
    await put(grant, html)
    wrong = deepcopy(payload)
    wrong["evaluations"][0]["result"]["rawValue"] = "forged"
    await complete(client, headers, pinned, wrong, 422)
    await complete(client, headers, pinned, payload)
    await process(domain, pinned, retry=True)
    fields = (await history(client, row.id))[0]["fields"]
    assert fields[0]["selectorVersionUuid"] == version["uuid"]
    assert fields[0]["status"] == "FIELD_CHANGED"
    assert fields[0]["baselineObservationId"] == old_observation_id

    repeated = await monitor(client, domain, headers, row.id, html + b" ")
    assert repeated["fields"][0]["selectorVersionUuid"] == next_version["uuid"]
    assert repeated["fields"][0]["taskId"] == fields[0]["taskId"]
    missing = await monitor(client, domain, headers, row.id, b"<p>no match</p>")
    assert missing["fields"][0]["status"] == "FIELD_MISSING"
    assert missing["fields"][0]["observationId"] is None
    assert await domain.count(FieldObservation) == await domain.count(ConcreteValue) == 4
    assert await domain.count(SelectorEvaluation, provenance="browser_agent_reported") == 5
    assert await domain.count(BusinessObject) == 1
    async with domain.factory() as session:
        canonical = await session.scalar(
            select(BusinessObjectFieldValue).where(
                BusinessObjectFieldValue.business_object_field_id == slot.object_field_id,
            )
        )
        assert canonical.value_json == "Canonical"
        tracking = await session.scalar(
            select(SourceObjectFieldTracking).where(SourceObjectFieldTracking.valid_to.is_(None))
        )
        assert tracking.baseline_observation_id == old_observation_id
        review = await session.get(Task, fields[0]["taskId"])
        workflow = await session.get(Workflow, review.workflow_id)
        assert review.status == TaskStatus.PENDING
        assert (
            workflow.status == "active"
            and workflow.source_snapshot_id == missing["sourceSnapshotId"]
        )


async def test_selector_failure_and_terminal_processing_failure_create_reviews(
    domain, client, minio
):
    from extraction.schemas.models import ExtractionRun
    from monitoring.queue import PROCESSING_LIMIT
    from tasks.schemas.models import TaskReason

    row = await source(domain, client)
    definition = tree(recipe(part(css("#first"), css("#second", order=1))))
    await add_tree(client, domain, row.id, None, definition)
    headers, _ = await agent(client, row.id)
    html = b'<p id="first">one</p><p id="second">two</p>'
    conflict = await monitor(client, domain, headers, row.id, html)
    assert conflict["fields"][0]["status"] == "FIELD_CONFLICT"
    assert conflict["fields"][0]["observationId"] is None
    async with domain.factory() as session:
        conflict_task = await session.get(Task, conflict["fields"][0]["taskId"])
        assert conflict_task.reason == TaskReason.VALUE_CONFLICT

    await enqueue(client, row.id)
    job = await claim(client, headers)
    grant, data = await prepare(client, headers, job, html, "a" * 64)
    await put(grant, html)
    await complete(client, headers, job, data)
    identity = UUID(job["jobId"])
    async with domain.factory.begin() as session:
        assert await MonitoringProcessor(session).acquire(identity)
        saved = await session.get(MonitoringJob, identity)
        saved.processing_attempts = PROCESSING_LIMIT - 1
    async with domain.factory.begin() as session:
        await MonitoringProcessor(session).retry_processing(identity, "last-flow")
    result = (await history(client, row.id))[0]
    assert result["status"] == "failed" and result["acquiredAt"]
    assert result["sourceSnapshotId"] == conflict["sourceSnapshotId"]
    assert result["fields"][0]["status"] == "FIELD_EXTRACTION_FAILED"
    async with domain.factory() as session:
        task = await session.get(Task, result["fields"][0]["taskId"])
        run = await session.get(ExtractionRun, result["extractionRunId"])
        assert task.reason == TaskReason.EXTRACTION_FAILED and run.status == "failed"
    assert await domain.count(BusinessObject) == 0


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org",
        "https://localhost",
        "https://127.0.0.1",
        "https://[::1]",
        "https://example.test",
        "https://user:pass@example.org",
        "https://example.org/?access_token=foo",
        "https://example.org:8443",
        "https://other.home.arpa",
    ],
)
async def test_unsafe_approval_urls(url):
    with pytest.raises(MonitoringError):
        origin(url)
