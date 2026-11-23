"""Exercise trusted enrollment, browser leases and the real Prefect processing queue."""

import asyncio
import json
import os
import sys
from datetime import timedelta
from hashlib import sha256
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_collections_postgres import domain as domain
from test_monitoring_orchestration import Service, eventually
from test_monitoring_orchestration import database as database
from test_monitoring_orchestration import prefect_server as prefect_server
from test_monitoring_postgres import (
    OPERATOR,
    add_tree,
    agent,
    complete,
    history,
    operation,
    prepare,
    put,
    review,
)
from test_monitoring_postgres import client as client
from test_monitoring_postgres import minio as minio
from test_selector_tree import css, part, recipe, tree

from extraction.schemas.common import utc_now
from extraction.schemas.models import FieldObservation
from monitoring.enrollment import MonitoringEnrollmentService
from monitoring.models import (
    ACTIVE,
    MonitoringAgentSource,
    MonitoringJob,
    MonitoringSource,
    SourceCheckRun,
)
from monitoring.onboarding_config import onboarding_config
from monitoring.queue import ATTEMPT_LIMIT, MonitoringQueue
from sources.schemas.api import SourceCreateRequest
from sources.schemas.enums import SourceState as State
from sources.schemas.models import Source, SourceCheckSchedule, SourceSnapshot, SourceStateHistory
from sources.services.sources import SourcesService

pytestmark = pytest.mark.asyncio
CLAIM = "/monitoring/jobs/claim?mode=trusted"


def configure(monkeypatch, **options):
    monkeypatch.setenv(
        "MONITORING_ONBOARDING_CONFIG",
        json.dumps({"mode": "trusted", "defaultSchedule": {"initialSpreadSeconds": 0}, **options}),
    )
    return onboarding_config()


async def register(domain, origin, *, source_type="HTML"):
    async with domain.factory.begin() as session:
        return await SourcesService(session, commit=False).create_source(
            SourceCreateRequest(type=source_type, url=f"{origin}/pages/{uuid4()}")
        )


async def trusted_agent(client):
    response = await client.post(
        "/monitoring/agents/register", headers=OPERATOR, json={"name": "Firefox", "trusted": True}
    )
    assert response.status_code == 201, response.text
    token = response.json()
    assert token["trusted"] and token["sourceIds"] == []
    return {"Authorization": "Bearer " + token["agentToken"]}


async def tick(domain, config):
    async with domain.factory.begin() as session:
        enrolled = await MonitoringEnrollmentService(
            session, config.default_schedule
        ).reconcile_trusted(config.batch_size, allow_http=config.trusted_allow_http)
        await session.flush()
        jobs = await MonitoringQueue(session).schedule_due("scheduler", config=config)
        return enrolled, [job.source_id for job in jobs]


async def test_continuous_enrollment_job_capacity_and_trusted_scope(domain, client, monkeypatch):
    config = configure(
        monkeypatch, batchSize=2, jobBatchSize=2, maxActiveJobs=2, maxActiveJobsPerOrigin=1
    )
    loopback = await register(domain, "https://127.0.0.1")
    internal = await register(domain, "https://burbot.internal")
    first = await register(domain, "https://example.org")
    same_site = await register(domain, "https://example.org")
    other = await register(domain, "https://example.net")
    pdf = await register(domain, "https://example.org", source_type="PDF")
    xlsx = await register(domain, "https://example.org", source_type="XLSX")
    disabled = await register(domain, "https://example.com")
    suspended = await register(domain, "https://example.com")
    custom_due = utc_now() + timedelta(hours=1)
    async with domain.factory.begin() as session:
        session.add(
            SourceCheckSchedule(
                source_id=disabled.id, enabled=False, interval_seconds=123, next_check_at=custom_due
            )
        )
        row = await session.get(Source, suspended.id)
        row.state = State.SUSPENDED

    ordinary, _ = await agent(client)
    assert (await client.post(CLAIM, headers=ordinary)).status_code == 403
    assert (await client.post(CLAIM)).status_code == 401
    assert await tick(domain, config) == (0, [])
    assert await tick(domain, config) == (2, [])

    headers = await trusted_agent(client)
    assert (await client.post(CLAIM, headers=headers)).status_code == 204
    assert await tick(domain, config) == (1, [first.id, other.id])
    assert await tick(domain, config) == (0, [])
    responses = await asyncio.gather(
        client.post(CLAIM, headers=headers), client.post(CLAIM, headers=headers)
    )
    assert sorted(response.status_code for response in responses) == [200, 204]
    claimed = next(response.json() for response in responses if response.status_code == 200)
    assert claimed["sourceId"] == first.id
    assert claimed["allowedOrigins"] == ["https://example.org"]
    assert claimed["navigation"] == {"mode": "trusted", "allowHttp": False}
    assert (await client.post("/monitoring/jobs/claim", headers=headers)).status_code == 204
    assert (
        await client.get(f"/monitoring/jobs/{claimed['jobId']}", headers=ordinary)
    ).status_code == 404
    assert await domain.count(MonitoringAgentSource) == 0

    newcomer = await register(domain, "https://another.example.org")
    assert await tick(domain, config) == (1, [])
    async with domain.factory.begin() as session:
        rows = await session.scalars(select(MonitoringJob).where(MonitoringJob.status.in_(ACTIVE)))
        assert {job.source_id for job in rows} == {first.id, other.id}
        for row in (loopback, internal, pdf, xlsx, suspended):
            assert await session.get(SourceCheckSchedule, row.id) is None
        for row in (same_site, newcomer):
            assert (await session.get(SourceCheckSchedule, row.id)).interval_seconds == 86400
        schedule = await session.get(SourceCheckSchedule, disabled.id)
        assert (schedule.enabled, schedule.interval_seconds, schedule.next_check_at) == (
            False,
            123,
            custom_due,
        )
    overview = (await client.get("/monitoring/overview", headers=OPERATOR)).json()
    assert overview["unsupportedSourceTypes"] == {"PDF": 1, "XLSX": 1}
    assert overview["enrolledSources"] == 5 and overview["approvedSources"] == 0
    assert overview["sourcesWithoutAuthorizedAgent"] == 0


async def test_failed_first_capture_retries_and_mode_is_opt_in(domain, client, monkeypatch):
    config = configure(monkeypatch)
    row = await register(domain, "http://example.org")
    headers = await trusted_agent(client)
    assert (await client.post(CLAIM, headers=headers)).status_code == 204
    assert await tick(domain, config) == (0, [])

    config = configure(monkeypatch, trustedAllowHttp=True)
    assert await tick(domain, config) == (1, [row.id])
    for attempt in range(1, ATTEMPT_LIMIT + 1):
        claim = await client.post(CLAIM, headers=headers)
        assert claim.status_code == 200, claim.text
        job = claim.json()
        assert job["allowedOrigins"] == ["http://example.org"]
        assert job["navigation"] == {"mode": "trusted", "allowHttp": True}
        failed = await client.post(
            operation(job, "fail"),
            headers=headers,
            json={"leaseId": job["leaseId"], "code": "HTTP_ERROR"},
        )
        assert failed.status_code == 200, failed.text
        assert failed.json()["errorCode"] == "HTTP_ERROR"
        assert failed.json()["attemptCount"] == attempt
        assert (await client.post(CLAIM, headers=headers)).status_code == 204
        assert await tick(domain, config) == (0, [])
        async with domain.factory.begin() as session:
            persisted = await session.get(MonitoringJob, UUID(job["jobId"]))
            assert await session.get(SourceSnapshot, persisted.source_snapshot_id or 0) is None
            current = await session.get(Source, row.id)
            if attempt < ATTEMPT_LIMIT:
                assert persisted.status == "retry_pending" and current.state == State.UNDISCOVERED
                assert persisted.available_at > utc_now()
                persisted.available_at = utc_now()
            else:
                assert persisted.status == "failed" and current.state == State.FAILED
                transitions = (
                    await session.execute(
                        select(SourceStateHistory.to_state, SourceStateHistory.reason)
                        .where(SourceStateHistory.source_id == row.id)
                        .order_by(SourceStateHistory.id)
                    )
                ).all()
                assert [state for state, _ in transitions] == [
                    State.UNDISCOVERED,
                    State.DISCOVERING,
                    State.FAILED,
                ]
                assert transitions[-1].reason == "HTTP_ERROR"
                schedule = await session.get(SourceCheckSchedule, row.id)
                assert schedule.last_checked_at is None and schedule.next_check_at > utc_now()
                schedule.next_check_at = utc_now()

    assert await domain.count(MonitoringJob, source_id=row.id) == 1
    assert await tick(domain, config) == (0, [row.id])
    strict = configure(monkeypatch, mode="strict")
    assert (await client.post(CLAIM, headers=headers)).status_code == 409
    response = await client.post(
        "/monitoring/agents/register",
        headers=OPERATOR,
        json={"name": "Scoped agent", "sourceIds": [row.id]},
    )
    assert response.status_code == 422
    async with domain.factory.begin() as session:
        assert await MonitoringQueue(session).cancel_stale(config=strict) == 1


async def test_prefect_validates_verified_rendered_evidence(
    domain, client, minio, prefect_server, tmp_path, monkeypatch
):
    configure(monkeypatch, maxActiveJobs=1)
    monkeypatch.setenv("DCKR_DATABASE_URL", os.environ["COLLECTIONS_TEST_DATABASE_URL"])
    row = await register(domain, "https://example.org")
    slot = domain.slot(await domain.make(name="Canonical"), "name")
    definition = tree(recipe(part(css("#evidence"))))
    await add_tree(client, domain, row.id, slot, definition)
    headers = await trusted_agent(client)
    assert (await client.post(CLAIM, headers=headers)).status_code == 204
    worker = Service(tmp_path / "worker.log", sys.executable, "-m", "monitoring.worker")

    async def with_status(status):
        checks = await history(client, row.id)
        for item in checks:
            assert item["status"] not in {"failed", "cancelled"}, item
            if item["status"] == status:
                return item

    try:
        worker.start()
        pending = await eventually(lambda: with_status("pending"))
        assert pending["schedulingFlowRunId"]
        response = await client.post(CLAIM, headers=headers)
        assert response.status_code == 200, response.text
        job = response.json()
        assert job["jobId"] == pending["jobId"]
        assert job["selectors"][0]["versionUuid"] == definition["versions"][0]["uuid"]
        html = b'<p id="evidence">Rendered by the browser</p>'
        grant, report = await prepare(client, headers, job, html, "a" * 64)
        await put(grant, html)
        for disallowed in ("https://127.0.0.1", "https://a.internal", "http://example.net"):
            await complete(client, headers, job, {**report, "pageUrl": disallowed}, 422)
        async with domain.factory() as session:
            assert (await session.get(Source, row.id)).state == State.UNDISCOVERED
        report["pageUrl"] = "https://example.net/rendered"
        assert (await complete(client, headers, job, report))["status"] == "uploaded"
        # The original policy is pinned for already verified uploads.
        configure(monkeypatch, mode="strict")
        await worker.stop()
        worker.start()
        finished = await eventually(lambda: with_status("completed"))
        assert finished["processingFlowRunId"] and finished["extractionRunId"]
        assert finished["changeStatus"] == "INITIAL_FETCH"
        assert finished["fields"][0]["evidenceStatus"] == "INITIAL_EVIDENCE"
        detail = await review(client, finished["fields"][0]["taskId"])
        assert detail["currentEvidence"] == "Rendered by the browser"
        assert detail["canonicalValue"] == "Canonical"
        async with domain.factory() as session:
            current = await session.get(Source, row.id)
            assert current.state == State.ACTIVE
            states = await session.scalars(
                select(SourceStateHistory.to_state)
                .where(SourceStateHistory.source_id == row.id)
                .order_by(SourceStateHistory.id)
            )
            assert list(states) == [
                State.UNDISCOVERED,
                State.DISCOVERING,
                State.VALIDATING,
                State.ACTIVE,
            ]
            snapshot = await session.get(SourceSnapshot, finished["sourceSnapshotId"])
            assert snapshot.page_url == report["pageUrl"]
            assert snapshot.content_hash == sha256(html).hexdigest()
            assert snapshot.structure_hash == "a" * 64
            schedule = await session.get(SourceCheckSchedule, row.id)
            assert schedule.next_check_at - schedule.last_checked_at == timedelta(hours=24)
            enrollment = await session.get(MonitoringSource, row.id)
            assert enrollment.origins == [] and enrollment.trusted_origin == "https://example.org"
        assert await domain.count(FieldObservation) == 1
        assert await domain.count(MonitoringJob) == 1
    except TimeoutError as error:
        raise AssertionError(worker.log.read_text() if worker.log.exists() else "") from error
    finally:
        await worker.stop()


async def test_prefect_backpressure_retains_uploads_in_postgres(
    domain, client, prefect_server, monkeypatch
):
    from prefect.client.orchestration import get_client
    from prefect.states import Cancelled

    from monitoring import flows, worker
    from monitoring.deployments import (
        POOL,
        PROCESS_DEPLOYMENT,
        PROCESS_QUEUE,
        UNFINISHED,
        run_filters,
    )
    from monitoring.deployments import (
        register as register_deployments,
    )

    config = configure(monkeypatch)
    monkeypatch.setattr(worker, "session_factory", domain.factory)
    monkeypatch.setattr(flows, "session_factory", domain.factory)
    monkeypatch.setattr(worker, "DISPATCH_BATCH", 1)
    row = await register(domain, "https://example.org")
    async with domain.factory.begin() as session:
        job = await MonitoringQueue(session).create_job(row.id, config=config)
        job.status = "uploaded"
    async with get_client() as prefect:
        await register_deployments(prefect)
        deployment = await prefect.read_deployment_by_name(PROCESS_DEPLOYMENT)
        queue = await prefect.read_work_queue_by_name(PROCESS_QUEUE, work_pool_name=POOL)
        queued = await prefect.create_flow_run_from_deployment(
            deployment.id, parameters={"job_id": str(uuid4())}
        )
        live = run_filters([deployment.id], UNFINISHED, queue_ids=[queue.id])
        assert await worker.dispatch_batch(prefect, deployment.id, queue.id, None) is None
        async with domain.factory() as session:
            assert (await session.get(SourceCheckRun, job.id)).processing_flow_run_id is None
        await prefect.set_flow_run_state(queued.id, Cancelled(), force=True)
        await worker.dispatch_batch(prefect, deployment.id, queue.id, None)
        (linked,) = await prefect.read_flow_runs(**live)
        assert linked.parameters["job_id"] == str(job.id)
        async with domain.factory() as session:
            assert (await session.get(SourceCheckRun, job.id)).processing_flow_run_id == str(
                linked.id
            )
