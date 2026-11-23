"""Drive the same REST protocol as Firefox against PostgreSQL and real MinIO."""

import asyncio
import os
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from runpy import run_path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from test_collections_postgres import database as database
from test_collections_postgres import domain as domain
from test_selector_tree import css, part, recipe, tree

from business_layer.schemas.models import BusinessObject, BusinessObjectFieldValue
from extraction.schemas import capture as capture_dto
from extraction.schemas.common import utc_now
from extraction.schemas.enums import ObservationStatus
from extraction.schemas.evidence import ExtractionIssue, GroundTruth, TokenClass
from extraction.schemas.models import ConcreteValue, FieldObservation
from extraction.schemas.selector import SelectorEvaluation
from extraction.schemas.selector_tree import SelectorVersionDefinition
from extraction.services.capture import CaptureService
from extraction.services.repositories import ExtractionRepository
from extraction.services.selector_resolver import HtmlSelectorRuntime, evaluate_selector_version
from extraction.services.tracking import update_tracking_from_observation
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
from tasks.schemas.models import Task, TaskReason, TaskReference, TaskStatus, Workflow

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
    from shared.database import get_session
    from tasks.api.database import get_session as get_task_session

    app = run_path(str(Path(__file__).resolve().parents[1] / "main.py"))["api"]

    async def sessions():
        async with domain.factory() as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    app.dependency_overrides[get_task_session] = sessions
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


async def review(client, task_id):
    response = await client.get(f"/monitoring/reviews/{task_id}", headers=OPERATOR)
    assert response.status_code == 200, response.text
    return response.json()


async def tasks_api(client, path, *, method="GET", expected=200, **kwargs):
    response = await client.request(method, f"/tasks{path}", headers=OPERATOR, **kwargs)
    assert response.status_code == expected, response.text
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

    assert await schedule() == []
    assert (await client.post("/monitoring/agents/heartbeat", headers=first)).status_code == 200
    planned = [job for batch in await asyncio.gather(schedule(), schedule()) for job in batch]
    assert [job.source_id for job in planned] == [due.id]
    assert await enqueue(client, due.id) == str(planned[0].id)
    assert (await history(client, due.id))[0]["status"] == "pending"
    base = "/monitoring/jobs"
    assert (await client.post(base + "/claim", headers=other)).status_code == 204
    assert (await client.post(base + "/claim")).status_code == 401
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
    assert await tasks_api(client, "/inbox/count") == 0
    assert (await monitor(client, domain, headers, row.id, html))["changeStatus"] == "UNCHANGED"
    assert await domain.count(SourceSnapshot, source_id=row.id) == 1
    assert await domain.count(Workflow, source_id=row.id) == 1
    assert await tasks_api(client, "/inbox/count") == 0

    second_html = b"<p>Second</p>"
    changed = await monitor(client, domain, headers, row.id, second_html)
    assert changed["changeStatus"] == "CONTENT_CHANGED" and changed["fields"] == []
    inbox = await tasks_api(client, "/inbox")
    content_task = inbox["items"][0]["task"]
    task_id = content_task["id"]
    assert inbox["total"] == 1 and content_task["reason"] == "source_changed"
    assert content_task["type"] == "review_source_change"
    expected = {
        "taskId": task_id,
        "taskStatus": "pending",
        "sourceId": row.id,
        "monitoringJobId": changed["jobId"],
        "changeTimestamp": changed["acquiredAt"].replace("+00:00", "Z"),
        "requiresReview": True,
        "reviewType": "source",
        "changeStatus": "CONTENT_CHANGED",
        "previousSnapshotId": checks[0]["sourceSnapshotId"],
        "currentSnapshotId": changed["sourceSnapshotId"],
        "previousContentHash": sha256(html).hexdigest(),
        "currentContentHash": sha256(second_html).hexdigest(),
        "previousStructureHash": "a" * 64,
        "currentStructureHash": "a" * 64,
    }
    assert await review(client, task_id) == expected
    refs = (await tasks_api(client, f"/{task_id}"))["references"]
    assert {(ref["reference_type"], ref["reference_id"]) for ref in refs} == {
        ("source", row.id),
        ("source_snapshot", checks[0]["sourceSnapshotId"]),
        ("source_snapshot", changed["sourceSnapshotId"]),
    }
    assert await domain.count(FieldObservation) == 0

    structure = await monitor(client, domain, headers, row.id, second_html, "b" * 64)
    assert structure["changeStatus"] == "STRUCTURE_CHANGED"
    structure_task = (await tasks_api(client, "/inbox"))["items"][0]["task"]
    structure_review = await review(client, structure_task["id"])
    assert structure_review["previousContentHash"] == structure_review["currentContentHash"]
    assert structure_review["previousStructureHash"] == "a" * 64
    assert structure_review["currentStructureHash"] == "b" * 64
    both = await monitor(client, domain, headers, row.id, b"<p>Third</p>", "c" * 64)
    assert both["changeStatus"] == "CONTENT_AND_STRUCTURE_CHANGED"
    assert await review(client, task_id) == expected  # Carry preserves original evidence.
    async with domain.factory.begin() as session:
        prior = await session.scalar(
            select(SourceSnapshot).order_by(SourceSnapshot.id.desc()).limit(1)
        )
        prior.representation_version = "other-version"
    assert (await monitor(client, domain, headers, row.id, html))["changeStatus"] == "INITIAL_FETCH"
    assert await tasks_api(client, "/inbox/count") == 3


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
    obj = await domain.make(name="B2B")
    slot = domain.slot(obj, "name")
    initial = tree(recipe(part(css("#name"))))
    etag = await add_tree(client, domain, row.id, slot, initial)
    headers, _ = await agent(client, row.id)
    original_evidence = "W projekcie mogą uczestniczyć przedsiębiorstwa MŚP"
    content = f'<meta charset="utf-8"><p id="name">{original_evidence}</p>'.encode()
    first = await monitor(client, domain, headers, row.id, content)
    first_field = first["fields"][0]
    old_observation_id = first_field["observationId"]
    assert first_field["status"] == "FIELD_NEW"
    assert first_field["evidenceStatus"] == "INITIAL_EVIDENCE"
    assert first_field["evidenceChanged"] is None
    initial_review = await review(client, first_field["taskId"])
    assert initial_review["canonicalValue"] == "B2B"
    assert initial_review["previousEvidence"] is None
    assert initial_review["currentEvidence"] == original_evidence

    # Accept the same observation already recorded as the latest check.
    async with domain.factory.begin() as session:
        repo = ExtractionRepository(session)
        obs = await repo.get(FieldObservation, old_observation_id)
        assert obs.status == ObservationStatus.DETECTED
        row_tracking = await repo.current_tracking(
            obs.source_field_tracking_id, obs.business_object_field_id
        )
        assert row_tracking.baseline_observation_id is None
        assert row_tracking.last_observation_id == obs.id
        obs.status = ObservationStatus.ACCEPTED
        advanced, changed = await update_tracking_from_observation(repo, row_tracking, obs)
        assert advanced.baseline_observation_id == obs.id and not changed
        assert (await update_tracking_from_observation(repo, advanced, obs)) == (advanced, False)

    unchanged = await monitor(client, domain, headers, row.id, content)
    assert unchanged["fields"][0]["status"] == "FIELD_UNCHANGED"
    assert unchanged["fields"][0]["taskId"] is None
    assert unchanged["fields"][0]["comparison"] == "accepted_baseline"
    assert unchanged["fields"][0]["previousObservationId"] == old_observation_id
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
    changed_review = await review(client, fields[0]["taskId"])
    assert {
        "businessObjectFieldId": slot.object_field_id,
        "canonicalValueId": slot.value_id,
        "canonicalValue": "B2B",
        "previousEvidence": original_evidence,
        "currentEvidence": "New",
        "evidenceStatus": "CHANGED",
        "evidenceChanged": True,
        "requiresReview": True,
    }.items() <= changed_review.items()

    repeated = await monitor(client, domain, headers, row.id, html + b" ")
    assert repeated["fields"][0]["selectorVersionUuid"] == next_version["uuid"]
    assert repeated["fields"][0]["taskId"] == fields[0]["taskId"]
    missing = await monitor(client, domain, headers, row.id, b"<p>no match</p>")
    assert missing["fields"][0]["status"] == "FIELD_MISSING"
    assert missing["fields"][0]["observationId"] is None
    missing_task = missing["fields"][0]["taskId"]
    missing_review = await review(client, missing_task)
    assert missing_review["evidenceStatus"] == "MISSING"
    assert missing_review["previousEvidence"] == original_evidence
    assert missing_review["currentEvidence"] is None
    assert missing_review["evidenceChanged"] is None
    assert missing_review["canonicalValue"] == "B2B"
    again = await monitor(client, domain, headers, row.id, b"<p>still no match</p>")
    assert again["fields"][0]["taskId"] == missing_task
    assert await domain.count(ExtractionIssue, code="VALUE_NOT_FOUND") == 2
    assert await domain.count(FieldObservation) == await domain.count(ConcreteValue) == 4
    assert await domain.count(SelectorEvaluation, provenance="browser_agent_reported") == 6
    assert await domain.count(SourceSnapshot, source_id=row.id) == 5
    assert await domain.count(Task) == 3
    assert await domain.count(BusinessObject) == 1
    async with domain.factory() as session:
        canonical = await session.scalar(
            select(BusinessObjectFieldValue).where(
                BusinessObjectFieldValue.business_object_field_id == slot.object_field_id,
            )
        )
        assert canonical.id == slot.value_id and canonical.value_json == "B2B"
        tracking = await session.scalar(
            select(SourceObjectFieldTracking).where(SourceObjectFieldTracking.valid_to.is_(None))
        )
        assert tracking.baseline_observation_id == old_observation_id
        review_task = await session.get(Task, fields[0]["taskId"])
        refs = await session.scalars(
            select(TaskReference).where(
                TaskReference.task_id == review_task.id,
                TaskReference.reference_type == "observation",
            )
        )
        assert {ref.reference_id for ref in refs} == {
            old_observation_id,
            fields[0]["observationId"],
        }
        workflow = await session.get(Workflow, review_task.workflow_id)
        assert review_task.status == TaskStatus.PENDING
        assert (
            workflow.status == "active" and workflow.source_snapshot_id == again["sourceSnapshotId"]
        )

    back = await monitor(client, domain, headers, row.id, html)
    changed_task_id = fields[0]["taskId"]
    assert back["fields"][0]["taskId"] == changed_task_id
    done = await tasks_api(
        client, f"/{changed_task_id}/status", method="PATCH", json={"status": "completed"}
    )
    assert done["status"] == "completed"
    completed = await review(client, changed_task_id)
    assert completed["canonicalValueId"] == slot.value_id
    assert completed["canonicalValue"] == "B2B"
    assert completed["taskStatus"] == "completed" and not completed["requiresReview"]
    assert completed["sourceId"] == row.id
    assert completed["selectorVersionId"] == fields[0]["selectorVersionId"]
    assert completed["selectorVersionUuid"] == version["uuid"]
    assert completed["observationId"] == fields[0]["observationId"]
    assert completed["baselineObservationId"] == completed["previousObservationId"]
    assert completed["previousObservationId"] == old_observation_id
    assert completed["comparison"] == "accepted_baseline"
    assert completed["changeTimestamp"] and completed["monitoringJobId"] == pinned["jobId"]
    async with domain.factory() as session:
        detected = await session.get(FieldObservation, fields[0]["observationId"])
        assert detected.status == ObservationStatus.DETECTED
    assert await domain.count(
        BusinessObjectFieldValue, business_object_field_id=slot.object_field_id
    ) == 1

    # A review reads the live canonical value after an explicit business edit.
    await domain.call(
        lambda service: service.data.assign_object_fields_values(
            obj.id,
            {slot.object_field_id: "B2C"},
            expected_value_ids={slot.object_field_id: slot.value_id},
        )
    )
    updated_review = await review(client, changed_task_id)
    assert updated_review["canonicalValue"] == "B2C"
    assert updated_review["previousEvidence"] == original_evidence
    assert updated_review["currentEvidence"] == "New"

    await monitor(client, domain, headers, row.id, b"<p>still no match</p>")
    for _ in range(2):
        same = await monitor(client, domain, headers, row.id, html)
        assert same["fields"][0]["taskId"] == changed_task_id
        assert same["fields"][0]["requiresReview"] is False
    assert await domain.count(Task) == 3


async def test_source_fallback_when_eligible_fields_are_unchanged(domain, client, minio):
    row = await source(domain, client)
    slot = domain.slot(await domain.make(name="Canonical"), "name")
    await add_tree(client, domain, row.id, slot, tree(recipe(part(css("#name")))))
    headers, _ = await agent(client, row.id)
    initial = b'<p id="name">First</p>'
    await monitor(client, domain, headers, row.id, initial)
    changed = initial.replace(b"First", b"Second")
    first_change = await monitor(client, domain, headers, row.id, changed)
    assert first_change["fields"][0]["status"] == "FIELD_CHANGED"
    assert await domain.count(Task, reason=TaskReason.SOURCE_CHANGED) == 0

    document_only = changed + b"<footer>Other content</footer>"
    second_change = await monitor(client, domain, headers, row.id, document_only, "b" * 64)
    assert second_change["fields"][0]["status"] == "FIELD_UNCHANGED"
    assert second_change["fields"][0]["taskId"] is None
    source_items = (await tasks_api(client, "/inbox", params={"reason": "source_changed"}))["items"]
    assert len(source_items) == 1
    detail = await review(client, source_items[0]["task"]["id"])
    assert detail["changeStatus"] == "CONTENT_AND_STRUCTURE_CHANGED"
    assert detail["previousSnapshotId"] == first_change["sourceSnapshotId"]
    assert detail["currentSnapshotId"] == second_change["sourceSnapshotId"]

    distinct = document_only.replace(b"Second", b"Third")
    latest = await monitor(client, domain, headers, row.id, distinct, "b" * 64)
    assert latest["fields"][0]["status"] == "FIELD_CHANGED"
    assert latest["fields"][0]["taskId"] != first_change["fields"][0]["taskId"]
    assert await domain.count(Task, reason=TaskReason.VALUE_CHANGED) == 2
    assert await domain.count(Task, reason=TaskReason.SOURCE_CHANGED) == 1


async def test_concurrent_processing_and_recurring_source_change(domain, client, minio):
    row = await source(domain, client)
    headers, _ = await agent(client, row.id)
    original, changed = b"<p>First</p>", b"<p>Second</p>"
    await monitor(client, domain, headers, row.id, original)
    await enqueue(client, row.id)
    job = await claim(client, headers)
    grant, data = await prepare(client, headers, job, changed, "a" * 64)
    await put(grant, changed)
    await complete(client, headers, job, data)
    identity = UUID(job["jobId"])
    async with domain.factory.begin() as session:
        assert await MonitoringProcessor(session).acquire(identity)

    async def finish():
        async with domain.factory.begin() as session:
            return await MonitoringProcessor(session).process(identity)

    assert sorted(await asyncio.gather(finish(), finish())) == [False, True]
    assert await domain.count(Workflow, source_id=row.id) == 2
    assert await domain.count(SourceSnapshot, source_id=row.id) == 2
    assert await domain.count(Task, reason=TaskReason.SOURCE_CHANGED) == 1
    task_id = (await tasks_api(client, "/inbox"))["items"][0]["task"]["id"]

    await monitor(client, domain, headers, row.id, original)
    await monitor(client, domain, headers, row.id, changed)
    assert await domain.count(Task, reason=TaskReason.SOURCE_CHANGED) == 2
    assert await tasks_api(client, "/inbox/count") == 2
    await tasks_api(client, f"/{task_id}/status", method="PATCH", json={"status": "completed"})
    await monitor(client, domain, headers, row.id, original)
    await monitor(client, domain, headers, row.id, changed)
    assert await domain.count(Task, reason=TaskReason.SOURCE_CHANGED) == 2
    assert await tasks_api(client, "/inbox/count") == 1
    assert not (await review(client, task_id))["requiresReview"]


async def test_task_inbox_filters_status_history_and_authorization(domain, client):
    row, other = await source(domain, client), await source(domain, client)
    first = SourceSnapshot(source_id=row.id)
    successor = SourceSnapshot(source_id=row.id)
    elsewhere = SourceSnapshot(source_id=other.id)
    async with domain.factory.begin() as session:
        session.add_all([first, successor, elsewhere])

    def task_body(snapshot, task_type="review_source_change", reason="value_changed"):
        return {
            "source_id": snapshot.source_id,
            "source_snapshot_id": snapshot.id,
            "type": task_type,
            "reason": reason,
        }

    async def start_workflow(snapshot, *tasks):
        return await tasks_api(
            client,
            f"/sources/{snapshot.source_id}/workflows",
            method="POST",
            expected=201,
            json={"source_snapshot_id": snapshot.id, "tasks": tasks},
        )

    initial = await start_workflow(first, task_body(first), task_body(first, "resolve_observation"))
    await start_workflow(elsewhere, task_body(elsewhere))
    workflow_id = initial["workflow"]["id"]
    first_task, stale_task = [task["id"] for task in initial["tasks"]]
    second_task = (await tasks_api(
        client,
        f"/workflows/{workflow_id}/tasks",
        method="POST",
        expected=201,
        json=task_body(first),
    ))["id"]
    await tasks_api(
        client,
        f"/workflows/{workflow_id}/tasks",
        method="POST",
        expected=409,
        json=task_body(successor),
    )
    async with domain.factory.begin() as session:
        created_at = utc_now()
        for task_id in (first_task, second_task):
            (await session.get(Task, task_id)).created_at = created_at

    filters = {"source_id": row.id, "type": "review_source_change", "reason": "value_changed"}
    assert await tasks_api(client, "/inbox/count") == 4
    assert await tasks_api(client, "/inbox/count", params=filters) == 2
    for offset, task_id in enumerate([second_task, first_task]):
        page = await tasks_api(client, "/inbox", params={**filters, "limit": 1, "offset": offset})
        assert (page["total"], page["limit"], page["offset"]) == (2, 1, offset)
        assert [item["task"]["id"] for item in page["items"]] == [task_id]
    end = await tasks_api(client, "/inbox", params={**filters, "offset": 2})
    assert end["total"] == 2 and end["items"] == []
    await tasks_api(client, "/inbox/count", params={"source_id": 0}, expected=422)

    async def transition(task_id, status, expected=200):
        return await tasks_api(
            client, f"/{task_id}/status", method="PATCH", expected=expected,
            json={"status": status},
        )

    await transition(first_task, "in_progress")
    failed = await transition(first_task, "failed")
    assert failed["completed_at"] and failed["started_at"]
    pending = await transition(first_task, "pending")
    assert pending["completed_at"] is None and pending["started_at"] is None
    await transition(first_task, "completed")
    await transition(first_task, "pending", 422)
    await transition(second_task, "cancelled")
    assert await tasks_api(client, "/inbox/count", params=filters) == 0

    active = await start_workflow(successor)
    workflows = (await tasks_api(client, f"/sources/{row.id}/workflows"))["items"]
    assert [(w["id"], w["status"]) for w in workflows] == [
        (active["workflow"]["id"], "active"), (workflow_id, "superseded")
    ]
    old = (await tasks_api(client, f"/workflows/{workflow_id}/tasks"))["items"]
    assert {task["id"]: task["status"] for task in old} == {
        first_task: "completed", second_task: "cancelled", stale_task: "cancelled",
    }
    assert (await tasks_api(client, f"/{stale_task}"))["workflow_id"] == workflow_id
    await transition(stale_task, "in_progress", 409)
    assert await tasks_api(client, "/inbox/count") == 1

    browser_headers, _ = await agent(client, row.id)
    for headers in ({}, browser_headers):
        for path in ("inbox", "inbox/count", str(first_task), f"workflows/{workflow_id}/tasks"):
            denied = await client.get(f"/tasks/{path}", headers=headers)
            assert denied.status_code == 401 and denied.headers["www-authenticate"] == "Bearer"
        denied = await client.patch(
            f"/tasks/{first_task}/status", headers=headers, json={"status": "cancelled"}
        )
        assert denied.status_code == 401


async def test_initial_evidence_uses_only_previous_observation_of_same_selector(
    domain,
    client,
    minio,
):
    row = await source(domain, client)
    obj = await domain.make(name="B2B")
    slot = domain.slot(obj, "name")
    primary = tree(recipe(part(css("#primary"))))
    secondary = tree(recipe(part(css("#secondary"))))
    await add_tree(client, domain, row.id, slot, primary)
    await add_tree(client, domain, row.id, slot, secondary)
    headers, _ = await agent(client, row.id)
    original = b'<p id="primary">Business participants</p><p id="secondary">Source conditions</p>'
    first = await monitor(client, domain, headers, row.id, original)
    assert len(first["fields"]) == 2
    assert {field["evidenceStatus"] for field in first["fields"]} == {"INITIAL_EVIDENCE"}
    assert all(field["requiresReview"] for field in first["fields"])
    assert await domain.count(Task, reason=TaskReason.MANUAL) == 2
    initial = {field["selectorUuid"]: field for field in first["fields"]}

    repeated = await monitor(client, domain, headers, row.id, original)
    assert {field["status"] for field in repeated["fields"]} == {"FIELD_UNCHANGED"}
    for field in repeated["fields"]:
        assert field["previousObservationId"] == initial[field["selectorUuid"]]["observationId"]
        assert field["comparison"] == "previous_observation"
        assert field["taskId"] is None and field["evidenceChanged"] is False
        assert field["baselineObservationId"] is None

    modified = original.replace(b"Business participants", b"New eligibility text")
    changed = await monitor(client, domain, headers, row.id, modified)
    assert {field["evidenceStatus"] for field in changed["fields"]} == {"CHANGED", "UNCHANGED"}
    pending = next(field for field in changed["fields"] if field["requiresReview"])
    assert pending["comparison"] == "previous_observation"
    detail = await review(client, pending["taskId"])
    assert detail["canonicalValue"] == "B2B"
    assert detail["previousEvidence"] == "Business participants"
    assert detail["currentEvidence"] == "New eligibility text"
    assert await domain.count(Task) == 3

    async with domain.factory() as session:
        tracking = await session.scalar(
            select(SourceObjectFieldTracking).where(SourceObjectFieldTracking.valid_to.is_(None))
        )
        assert tracking.baseline_observation_id is None
        assert tracking.last_checked_at.isoformat() == changed["acquiredAt"].replace("Z", "+00:00")
    assert await domain.count(FieldObservation, status=ObservationStatus.DETECTED) == 6
    assert (
        await domain.count(BusinessObjectFieldValue, business_object_field_id=slot.object_field_id)
        == 1
    )


async def test_first_monitoring_compares_the_raw_human_confirmed_baseline(domain, client, minio):
    row = await source(domain, client)
    obj = await domain.make(name="B2B")
    slot = domain.slot(obj, "name")
    agent_headers, _ = await agent(client, row.id)
    selected = "Business participants"
    html = f'<p id="evidence">{selected}</p>'.encode()
    snapshot = (await monitor(client, domain, agent_headers, row.id, html))["sourceSnapshotId"]
    await add_tree(client, domain, row.id, slot, tree(recipe(part(css("#evidence")))))

    async with domain.factory.begin() as session:
        service = CaptureService(session, commit=False)
        await service.repo.get_or_create(TokenClass, {"id": "text"}, {"name": "Text"})
        run = await service.create_run(
            capture_dto.CreateRunRequest(snapshot_id=snapshot, extractor_version="manual")
        )
        accepted = await service.register_capture(
            run.id,
            capture_dto.CaptureRequest.model_validate(
                {
                    "capture_key": "human-confirmed",
                    "scopes": [
                        {
                            "client_key": "document",
                            "name": "ROOT",
                            "selector": {
                                "type": "CSS",
                                "value": "html",
                                "discovered_by": "AUTOMATIC",
                            },
                        }
                    ],
                    "scope_instances": [
                        {
                            "client_key": "document",
                            "scope_client_key": "document",
                            "root_element_client_key": "document",
                        }
                    ],
                    "elements": [
                        {
                            "client_key": "document",
                            "element_from": "HTML",
                            "html": {"tag_name": "html"},
                        }
                    ],
                    "values": [
                        {
                            "client_key": "selected",
                            "scope_instance_client_key": "document",
                            "element_client_key": "document",
                            "business_entity_field_id": domain.fields["name"],
                            "business_object_id": obj.id,
                            "token_class_id": "text",
                            "raw_value": selected,
                            "normalized_value": "B2B",
                            "confirmed_by_human": True,
                        }
                    ],
                }
            ),
        )
    evidence = (await monitor(client, domain, agent_headers, row.id, html))["fields"][0]
    assert evidence["status"] == "FIELD_UNCHANGED"
    assert evidence["comparison"] == "accepted_baseline"
    assert evidence["baselineObservationId"] == accepted.observation_ids_by_client_key["selected"]
    assert evidence["requiresReview"] is False and evidence["taskId"] is None
    assert await domain.count(GroundTruth) == 1
    assert (
        await domain.count(BusinessObjectFieldValue, business_object_field_id=slot.object_field_id)
        == 1
    )


async def test_monitoring_preserves_success_for_evidence_in_different_formats(
    domain, client, minio
):
    row = await source(domain, client)
    fields = [
        ("PROG.07.09-IP.01", "PROG.07.09-IP.01-0014/23-00"),
        ("Program Kompetencji 3.0", "Program Kompetencji 3.0"),
        ("region|miasto|Przykład", "Regulamin projektu.pdf"),
        ("https://example.org/announcement", None),
        ("2027-12-31", "31.12.2027"),
        ("https://example.org/application", None),
        ("03/SEED/2026", "03/SEED/2026 IV kwartał 2026 Listopad 2026 Styczeń 2027"),
        ("B2B", "Opis grupy docelowej przedsiębiorstw MŚP"),
        ("2024-01-01", "01.01.2024"),
    ]
    snippets, expected = ['<meta charset="utf-8">'], {}
    for position, (canonical, raw) in enumerate(fields):
        obj = await domain.make(name=canonical)
        slot = domain.slot(obj, "name")
        element_id = f"field-{position}"
        definition = tree(recipe(part(css(f"#{element_id}"))))
        await add_tree(client, domain, row.id, slot, definition)
        expected[definition["selector"]["uuid"]] = (slot, raw)
        if raw is not None:
            snippets.append(f'<p id="{element_id}">{raw}</p>')

    headers, _ = await agent(client, row.id)
    check = await monitor(client, domain, headers, row.id, "".join(snippets).encode())
    assert len(check["fields"]) == 9
    async with domain.factory() as session:
        repo = ExtractionRepository(session)
        for result in check["fields"]:
            slot, raw = expected[result["selectorUuid"]]
            evaluation = await session.get(SelectorEvaluation, result["evaluationId"])
            canonical = await session.get(BusinessObjectFieldValue, slot.value_id)
            assert canonical.value_json == slot.value
            assert evaluation.provenance == "browser_agent_reported"
            if raw is None:
                assert result["evidenceStatus"] == "MISSING"
                assert evaluation.result_json["status"] == "not_found"
                assert result["observationId"] is None
            else:
                assert result["evidenceStatus"] == "INITIAL_EVIDENCE"
                assert evaluation.result_json["status"] == "success"
                evidence = await repo.get(FieldObservation, result["observationId"])
                assert evidence.status == ObservationStatus.DETECTED
                assert (await repo.observation_value(evidence)).raw_value == raw
    assert await domain.count(FieldObservation) == 7
    assert await domain.count(ExtractionIssue, code="VALUE_NOT_FOUND") == 2


@pytest.mark.parametrize(
    "locator,outcome,evidence_status,reason",
    [
        (".same", "FIELD_AMBIGUOUS", "AMBIGUOUS", "value_conflict"),
        ("[", "FIELD_EXTRACTION_FAILED", "EXTRACTION_FAILED", "extraction_failed"),
    ],
)
async def test_selector_evaluation_failure_review(
    domain, client, minio, locator, outcome, evidence_status, reason
):
    row = await source(domain, client)
    await add_tree(client, domain, row.id, None, tree(recipe(part(css(locator)))))
    headers, _ = await agent(client, row.id)
    html = b'<p class="same">One</p><p class="same">Two</p>'
    result = (await monitor(client, domain, headers, row.id, html))["fields"][0]
    assert result["status"] == outcome and result["observationId"] is None
    task_id = result["taskId"]
    assert (await tasks_api(client, f"/{task_id}"))["reason"] == reason
    detail = await review(client, task_id)
    assert detail["reviewType"] == "field" and detail["evidenceStatus"] == evidence_status
    assert detail["currentEvidence"] is None
    assert detail["evaluationId"] == result["evaluationId"]
    assert detail["selectorVersionId"] == result["selectorVersionId"]


async def test_selector_failure_and_terminal_processing_failure_create_reviews(
    domain, client, minio
):
    from extraction.schemas.models import ExtractionRun
    from monitoring.queue import PROCESSING_LIMIT

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
