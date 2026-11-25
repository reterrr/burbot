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
from test_selector_tree import css, part, recipe, tree, uuid

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
from monitoring.models import MonitoringJob, MonitoringUpload, SourceCheckRun
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


async def review(client, task_id):
    response = await client.get(f"/monitoring/reviews/{task_id}", headers=OPERATOR)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


async def field_review(client, source_id, check, field):
    path = f"/monitoring/sources/{source_id}/review"
    full = await client.get(path, params={"checkId": check["jobId"]}, headers=OPERATOR)
    assert full.status_code == 200, full.text
    captured = await client.get(
        f"{path}/{check['jobId']}/{field['selectorUuid']}", headers=OPERATOR
    )
    assert captured.status_code == 200, captured.text
    context = next(
        row for row in full.json()["fields"] if row["selectorUuid"] == field["selectorUuid"]
    )
    return {**context, **captured.json(), "snapshot": full.json()["snapshot"]}


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
                "businessEntityFieldId": (
                    slot.business_entity_field_id if slot else domain.fields["name"]
                ),
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
    assert initial_review["selector"]["version"]["status"] == "active"
    assert initial_review["selector"]["identity"] == initial["selector"]

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
    changed = (await history(client, row.id))[0]
    fields = changed["fields"]
    assert fields[0]["selectorVersionUuid"] == version["uuid"]
    assert fields[0]["status"] == "FIELD_CHANGED"
    assert fields[0]["baselineObservationId"] == old_observation_id
    assert fields[0]["taskId"] == first_field["taskId"]
    changed_review = await field_review(client, row.id, changed, fields[0])
    assert changed_review["selector"] == {
        "identity": {
            key: value for key, value in initial["selector"].items() if key != "activeVersionUuid"
        },
        "versionId": fields[0]["selectorVersionId"],
        "version": {**version, "status": "superseded"},
    }
    execution = changed_review["evaluation"]
    assert execution["result"] == payload["evaluations"][0]["result"]
    assert execution["provenance"] == "browser_agent_reported"
    assert execution["pageUrl"] == row.url
    assert execution["sourceSnapshotId"] == changed_review["snapshot"]["id"]
    assert execution["extractionRunId"] == changed_review["extractionRunId"]
    assert {
        "businessObjectFieldId": slot.object_field_id,
        "canonicalValueId": slot.value_id,
        "canonicalValue": "B2B",
        "previousEvidence": original_evidence,
        "currentEvidence": "New",
    }.items() <= changed_review.items()
    assert fields[0]["evidenceStatus"] == "CHANGED"
    assert fields[0]["evidenceChanged"] and fields[0]["requiresReview"]

    repeated = await monitor(client, domain, headers, row.id, html + b" ")
    assert repeated["fields"][0]["selectorVersionUuid"] == next_version["uuid"]
    assert repeated["fields"][0]["taskId"] == fields[0]["taskId"]
    missing = await monitor(client, domain, headers, row.id, b"<p>no match</p>")
    assert missing["fields"][0]["status"] == "FIELD_MISSING"
    assert missing["fields"][0]["observationId"] is None
    missing_task = missing["fields"][0]["taskId"]
    assert missing_task == first_field["taskId"]
    missing_review = await field_review(client, row.id, missing, missing["fields"][0])
    assert missing["fields"][0]["evidenceStatus"] == "MISSING"
    assert missing_review["previousEvidence"] == original_evidence
    assert missing_review["currentEvidence"] is None
    assert missing["fields"][0]["evidenceChanged"] is None
    assert missing_review["canonicalValue"] == "B2B"
    again = await monitor(client, domain, headers, row.id, b"<p>still no match</p>")
    assert again["fields"][0]["taskId"] == missing_task
    assert await domain.count(ExtractionIssue, code="VALUE_NOT_FOUND") == 2
    assert await domain.count(FieldObservation) == await domain.count(ConcreteValue) == 4
    assert await domain.count(SelectorEvaluation, provenance="browser_agent_reported") == 6
    assert await domain.count(SourceSnapshot, source_id=row.id) == 5
    assert await domain.count(Task) == 1
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

    # A review reads the live canonical value after an explicit business edit.
    await domain.call(
        lambda service: service.data.assign_object_fields_values(
            obj.id,
            {slot.object_field_id: "B2C"},
            expected_value_ids={slot.object_field_id: slot.value_id},
        )
    )
    updated_review = await field_review(client, row.id, changed, fields[0])
    assert updated_review["canonicalValue"] == "B2C"
    assert updated_review["previousEvidence"] == original_evidence
    assert updated_review["currentEvidence"] == "New"
    assert updated_review["selector"] == changed_review["selector"]
    assert updated_review["evaluation"] == changed_review["evaluation"]
    assert updated_review["snapshot"] == changed_review["snapshot"]

    back = await monitor(client, domain, headers, row.id, html)
    assert back["fields"][0]["taskId"] == fields[0]["taskId"]
    async with domain.factory.begin() as session:
        done = await session.get(Task, back["fields"][0]["taskId"])
        done.status = TaskStatus.COMPLETED
        done.completed_at = utc_now()
    for _ in range(2):
        same = await monitor(client, domain, headers, row.id, html)
        assert same["fields"][0]["taskId"] == done.id
        assert same["fields"][0]["requiresReview"] is False
    assert await domain.count(Task) == 1
    assert (await review(client, done.id))["requiresReview"] is False


async def test_review_checks_execution_links_and_keeps_legacy_comparisons(domain, client, minio):
    row = await source(domain, client)
    xpath = {"uuid": uuid(), "kind": "xpath", "order": 1, "expression": "//p"}
    definition = tree(
        recipe(part(css("#required"), xpath)),
        recipe(part(css("#backup")), order=1),
    )
    await add_tree(client, domain, row.id, None, definition)
    headers, _ = await agent(client, row.id)
    first = await monitor(client, domain, headers, row.id, b"<p>First</p><p>Second</p>")
    field = first["fields"][0]
    task_id = field["taskId"]
    path = f"/monitoring/reviews/{task_id}"
    assert (await client.get(path)).status_code == 401
    assert (await client.get(path, headers=headers)).status_code == 401
    assert (await client.patch(path, headers=OPERATOR)).status_code == 405
    detail = await review(client, task_id)
    assert detail["currentEvidence"] is None
    assert detail["evidenceStatus"] == "AMBIGUOUS"
    assert detail["source"] == {"id": row.id, "url": row.url}
    assert detail["snapshot"]["id"] == first["sourceSnapshotId"]
    assert "storage_key" not in detail["snapshot"]
    assert detail["selector"]["version"]["recipes"] == definition["versions"][0]["recipes"]
    result = detail["evaluation"]["result"]
    assert result["status"] == "ambiguous"
    recipes = result["recipeResults"]
    assert [recipe["status"] for recipe in recipes] == ["ambiguous", "not_found"]
    locators = recipes[0]["partResults"][0]["locatorResults"]
    assert [(locator["status"], locator["matchCount"]) for locator in locators] == [
        ("not_found", 0),
        ("ambiguous", 2),
    ]

    async with domain.factory.begin() as session:
        check = await session.get(SourceCheckRun, UUID(first["jobId"]))
        task = await session.get(Task, task_id)
        task.metadata_json = {"monitoringJobId": first["jobId"]}
        check.field_results = [
            {
                "taskId": task_id,
                "status": field["status"],
                "evaluationId": field["evaluationId"],
            }
        ]
    legacy = await review(client, task_id)
    assert legacy["selector"] == detail["selector"]
    assert legacy["evaluation"] == detail["evaluation"]

    async with domain.factory.begin() as session:
        check = await session.get(SourceCheckRun, UUID(first["jobId"]))
        check.field_results = [{**field, "evaluationId": None}]
    unevaluated = await review(client, task_id)
    assert unevaluated["selector"] == detail["selector"]
    assert unevaluated["evaluation"] is None

    second = await monitor(client, domain, headers, row.id, b"<span>No matching element</span>")
    assert second["sourceSnapshotId"] != first["sourceSnapshotId"]
    assert second["fields"][0]["status"] == "FIELD_MISSING"
    async with domain.factory.begin() as session:
        check = await session.get(SourceCheckRun, UUID(first["jobId"]))
        check.field_results = [{**field, "evaluationId": second["fields"][0]["evaluationId"]}]
    invalid = await review(client, task_id)
    assert invalid["selector"] == detail["selector"]
    assert invalid["evaluation"] is None
    assert invalid["snapshot"]["id"] == first["sourceSnapshotId"]

    async with domain.factory.begin() as session:
        job = await session.get(MonitoringJob, UUID(first["jobId"]))
        job.source_snapshot_id = second["sourceSnapshotId"]
    assert (await client.get(path, headers=OPERATOR)).status_code == 404


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
    assert await domain.count(Task, reason=TaskReason.MANUAL) == 1
    assert len({field["taskId"] for field in first["fields"]}) == 1
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
    detail = await field_review(client, row.id, changed, pending)
    assert detail["canonicalValue"] == "B2B"
    assert detail["previousEvidence"] == "Business participants"
    assert detail["currentEvidence"] == "New eligibility text"
    assert await domain.count(Task) == 1

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
    assert (await review(client, conflict["fields"][0]["taskId"]))["evaluation"]["result"][
        "status"
    ] == "conflict"
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
    unavailable = await review(client, result["fields"][0]["taskId"])
    assert unavailable["selector"] is None and unavailable["evaluation"] is None
    assert unavailable["extractionRunId"] == result["extractionRunId"]
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
