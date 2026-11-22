import asyncio
import json
import logging
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from test_collections_postgres import domain as domain
from test_monitoring_orchestration import database as database
from test_monitoring_orchestration import prefect_server as prefect_server
from test_monitoring_postgres import (
    OPERATOR,
    agent,
    claim,
    history,
)
from test_monitoring_postgres import client as client
from test_monitoring_postgres import minio as minio

from extraction.schemas.common import utc_now
from monitoring.discovery import ProbeResult
from monitoring.models import MonitoringJob, MonitoringSource, OnboardingItem
from monitoring.onboarding import reserve_origin, run_onboarding_batch
from monitoring.onboarding_config import onboarding_config
from monitoring.queue import MonitoringQueue
from sources.schemas.api import SourceCreateRequest
from sources.schemas.enums import SourceState as State
from sources.schemas.models import Source, SourceCheckSchedule, SourceStateHistory
from sources.services.sources import SourcesService

pytestmark = pytest.mark.asyncio
LOGGER = logging.getLogger(__name__)
SITE = "https://example.org"


def configure(monkeypatch, *, policies=None, **options):
    monkeypatch.setenv(
        "MONITORING_ONBOARDING_CONFIG",
        json.dumps(
            {
                "policies": policies or {"official": {"origins": [SITE], "autoEnroll": True}},
                "perOriginIntervalSeconds": 0,
                **options,
            }
        ),
    )
    return onboarding_config()


async def register(domain, site=SITE, *, source_type="HTML"):
    async with domain.factory.begin() as session:
        return await SourcesService(session, commit=False).create_source(
            SourceCreateRequest(type=source_type, url=f"{site}/projects/{uuid4()}")
        )


async def submit(client, **request):
    res = await client.post(
        "/monitoring/onboarding/runs", headers=OPERATOR, json={"policy": "official", **request}
    )
    assert res.status_code == 202, res.text
    return res.json()["runId"]


async def progress(client, run_id, **query):
    res = await client.get(f"/monitoring/onboarding/runs/{run_id}", params=query, headers=OPERATOR)
    assert res.status_code == 200, res.text
    return res.json()


async def valid_probe(url, policy, reserve, timeout):
    return ProbeResult(State.ACTIVE, "HTML_VALIDATED", http_status=200, visited_origins=(SITE,))


async def tick(domain, config, probe=valid_probe):
    return await run_onboarding_batch(domain.factory, config, LOGGER, probe=probe)


async def test_bulk_400_uses_bounded_batches_and_persists_lifecycle(domain, client, monkeypatch):
    config = configure(monkeypatch, batchSize=40, defaultSchedule={"initialSpreadSeconds": 3600})
    first = await register(domain)
    excluded = await register(domain, "https://other.example.org")
    pdf = await register(domain, source_type="PDF")
    async with domain.factory.begin() as session:
        session.add_all([Source(type="HTML", url=f"{SITE}/batch/{n}") for n in range(399)])
    request_id = str(uuid4())
    payload = {"sourceType": "HTML", "sourceState": "UNDISCOVERED", "requestId": request_id}
    res = await client.post(
        "/monitoring/onboarding/preview", headers=OPERATOR, json={"policy": "official", **payload}
    )
    assert res.status_code == 200, res.text
    assert res.json()["counts"] == {
        "selected": 401,
        "unsupported": 0,
        "discoverable": 400,
        "approvedIfActive": 400,
        "needsApproval": 0,
        "outsidePolicy": 1,
    }
    assert await domain.count(MonitoringSource) == 0
    run_id = await submit(client, **payload)
    assert await submit(client, **payload) == run_id
    altered = await client.post(
        "/monitoring/onboarding/runs",
        headers=OPERATOR,
        json={"policy": "official", **payload, "batchSize": 17},
    )
    assert altered.status_code == 409
    assert (await progress(client, run_id))["status"] == "pending"
    start = utc_now()
    for _ in range(12):
        assert await tick(domain, config) <= 40
    result = await progress(client, run_id, limit=2)
    assert result["status"] == "completed"
    assert result["counts"] == {"enrolled": 400, "needs_approval": 1}
    assert result["nextAfterSourceId"] == result["items"][-1]["sourceId"]
    next_page = await progress(client, run_id, afterSourceId=result["nextAfterSourceId"], limit=2)
    assert min(item["sourceId"] for item in next_page["items"]) > result["nextAfterSourceId"]

    async with domain.factory() as session:
        states = list(
            await session.scalars(
                select(SourceStateHistory.to_state)
                .where(SourceStateHistory.source_id == first.id)
                .order_by(SourceStateHistory.id)
            )
        )
        assert states == [State.UNDISCOVERED, State.DISCOVERING, State.VALIDATING, State.ACTIVE]
        for identity in [excluded.id, pdf.id]:
            assert (await session.get(Source, identity)).state == State.UNDISCOVERED
        ordered = list(await session.scalars(select(SourceCheckSchedule.next_check_at)))
        assert len(ordered) == 400
        assert min(ordered) >= start and max(ordered) < utc_now() + timedelta(hours=1)
        assert max(ordered) - min(ordered) > timedelta(minutes=50)
        assert await session.scalar(select(func.count()).select_from(MonitoringJob)) == 0

    another_run = await submit(client, sourceIds=[first.id])
    await tick(domain, config)
    assert (await progress(client, another_run))["counts"] == {"enrolled": 1}
    async with domain.factory() as session:
        assert (await session.get(SourceCheckSchedule, first.id)).next_check_at in ordered
    assert await domain.count(SourceStateHistory, source_id=first.id) == 4

    pdf_run = await submit(client, sourceType="PDF", sourceIds=[pdf.id])
    await tick(domain, config)
    assert (await progress(client, pdf_run))["items"][0]["diagnostics"]["code"] == (
        "UNSUPPORTED_SOURCE_TYPE"
    )
    report = await client.get("/monitoring/overview", headers=OPERATOR)
    assert report.status_code == 200, report.text
    assert report.json()["sourcesByType"] == {"HTML": 401, "PDF": 1}
    assert report.json()["discoveredSources"] == report.json()["validatedSources"] == 400
    assert report.json()["sourcesWithoutAuthorizedAgent"] == 400


async def test_continuous_discovery_requires_approval_and_preserves_custom_schedule(
    domain, client, monkeypatch
):
    config = configure(
        monkeypatch,
        policies={"official": {"origins": [SITE], "continuous": True}},
        batchSize=1,
    )
    first = await register(domain)
    await tick(domain, config)
    newcomer = await register(domain)
    for _ in range(3):
        await tick(domain, config)
    assert await domain.count(Source, state=State.ACTIVE) == 2
    assert await domain.count(MonitoringSource) == 0

    check = utc_now() - timedelta(days=1)
    next_check = utc_now() + timedelta(hours=2)
    async with domain.factory.begin() as session:
        session.add(
            SourceCheckSchedule(
                source_id=first.id,
                enabled=False,
                interval_seconds=7200,
                last_checked_at=check,
                next_check_at=next_check,
            )
        )
    config = configure(
        monkeypatch,
        policies={"official": {"origins": [SITE], "continuous": True, "autoEnroll": True}},
        batchSize=1,
    )
    for _ in range(4):
        await tick(domain, config)
    async with domain.factory() as session:
        schedule = await session.get(SourceCheckSchedule, first.id)
        assert (schedule.enabled, schedule.interval_seconds) == (False, 7200)
        assert (schedule.last_checked_at, schedule.next_check_at) == (check, next_check)
        assert (await session.get(SourceCheckSchedule, newcomer.id)).enabled
    runs = (await client.get("/monitoring/onboarding/runs", headers=OPERATOR)).json()["runs"]
    assert len(runs) == 1 and runs[0]["continuous"]


async def test_per_source_approval_and_recoverable_retries(domain, client, monkeypatch):
    config = configure(
        monkeypatch,
        policies={"official": {"origins": [SITE]}},
        discoveryAttempts=2,
        retryBaseSeconds=30,
    )
    row = await register(domain)
    identity = UUID(await submit(client, sourceIds=[row.id], approveSelected=True))
    reset_time = utc_now() + timedelta(minutes=5)
    seen = 0

    async def transient(url, policy, reserve, timeout):
        nonlocal seen
        seen += 1
        return ProbeResult(State.FAILED, "HTTP_RETRYABLE", True, 429, retry_at=reset_time)

    assert await tick(domain, config, transient) == 1
    item = (await progress(client, identity))["items"][0]
    assert item["sourceState"] == "DISCOVERING" and item["attempts"] == 1
    assert item["diagnostics"] == {
        "code": "HTTP_RETRYABLE",
        "retryable": True,
        "httpStatus": 429,
        "redirects": 0,
    }
    assert await tick(domain, config, transient) == 0 and seen == 1
    async with domain.factory.begin() as session:
        pending = await session.get(OnboardingItem, (identity, row.id))
        assert pending.available_at == reset_time
        pending.available_at = utc_now()
    await tick(domain, config, transient)
    assert (await progress(client, identity))["items"][0]["sourceState"] == "FAILED"
    res = await client.post(f"/monitoring/onboarding/runs/{identity}/retry", headers=OPERATOR)
    assert res.status_code == 202 and res.json()["requeued"] == 1
    await tick(domain, config)
    assert (await progress(client, identity))["counts"] == {"enrolled": 1}
    assert await domain.count(MonitoringSource, enabled=True) == 1
    async with domain.factory() as session:
        history_states = list(
            await session.scalars(
                select(SourceStateHistory.to_state)
                .where(SourceStateHistory.source_id == row.id)
                .order_by(SourceStateHistory.id)
            )
        )
    assert history_states == [
        State.UNDISCOVERED,
        State.DISCOVERING,
        State.FAILED,
        State.DISCOVERING,
        State.VALIDATING,
        State.ACTIVE,
    ]


async def test_rate_reservation_persists_between_transactions(domain):
    assert await reserve_origin(domain.factory, SITE, 30, 1) is None
    blocked_until = await reserve_origin(domain.factory, SITE, 30, 1)
    assert blocked_until > utc_now()
    assert await reserve_origin(domain.factory, "https://www.example.org", 30, 1) is None


async def test_online_capacity_agent_scope_and_round_robin_by_due_time(domain, client, monkeypatch):
    headers, agent_id = await agent(client)
    config = configure(
        monkeypatch,
        policies={
            "official": {
                "origins": [SITE, "https://other.example.org"],
                "autoEnroll": True,
                "continuous": True,
                "agentIds": [agent_id],
            }
        },
        defaultSchedule={"initialSpreadSeconds": 0},
        maxActiveJobs=2,
        maxActiveJobsPerOrigin=1,
        jobBatchSize=2,
    )
    rows = [
        await register(domain),
        await register(domain),
        await register(domain, "https://other.example.org"),
    ]
    await tick(domain, config)
    async with domain.factory.begin() as session:
        now = utc_now()
        for index, row in enumerate(rows):
            schedule = await session.get(SourceCheckSchedule, row.id)
            schedule.next_check_at = now - timedelta(minutes=len(rows) - index)

    async def schedule():
        async with domain.factory.begin() as session:
            return await MonitoringQueue(session).schedule_due(config=config)

    assert await schedule() == []
    assert (await client.post("/monitoring/agents/heartbeat", headers=headers)).status_code == 200
    batches = await asyncio.gather(schedule(), schedule())
    jobs = [job for batch in batches for job in batch]
    assert {job.source_id for job in jobs} == {rows[0].id, rows[2].id}
    assert await schedule() == []

    unscoped, _ = await agent(client)
    assert (await client.post("/monitoring/jobs/claim", headers=unscoped)).status_code == 204
    claimed = await claim(client, headers)
    assert claimed["sourceId"] == rows[0].id
    url = f"/monitoring/agents/{agent_id}/sources"
    assert (
        await client.put(url, json={"removeSourceIds": [rows[0].id]}, headers=headers)
    ).status_code == 401
    assert (
        await client.put(url, json={"removeSourceIds": [rows[0].id]}, headers=OPERATOR)
    ).status_code == 200
    assert (
        await client.get(f"/monitoring/jobs/{claimed['jobId']}", headers=headers)
    ).status_code == 404
    check = (await history(client, rows[0].id))[0]
    assert check["status"] == "retry_pending" and check["errorCode"] == "AGENT_SCOPE_REVOKED"
    await tick(domain, config)
    coverage = (await client.get("/monitoring/coverage", headers=OPERATOR)).json()
    assert coverage["sources"] == [
        {
            "sourceId": rows[0].id,
            "hasAuthorizedAgent": False,
            "hasOnlineAgent": False,
        }
    ]
    assert (
        await client.put(url, json={"policy": "official", "limit": 1}, headers=OPERATOR)
    ).json()["nextAfterSourceId"] == rows[0].id
    assert (await client.get("/monitoring/coverage", headers=OPERATOR)).json() == coverage
    assert (
        await client.put(url, json={"addSourceIds": [rows[0].id]}, headers=OPERATOR)
    ).status_code == 200
    assert (await client.get("/monitoring/coverage", headers=OPERATOR)).json()["sources"] == []

    async with domain.factory.begin() as session:
        completed = await session.get(MonitoringJob, UUID(claimed["jobId"]))
        completed.status = "completed"
        check = await session.get(SourceCheckSchedule, rows[0].id)
        check.next_check_at = utc_now() + timedelta(hours=2)
    assert [job.source_id for job in await schedule()] == [rows[1].id]


async def test_prefect_onboards_and_processes_a_controlled_html_source(
    prefect_server, domain, client, minio, tmp_path, monkeypatch
):
    """Run the real Worker and HTTPS validation with a test-only route to a local server."""
    import os
    import shutil
    import ssl
    import subprocess
    import sys

    from test_monitoring_orchestration import Service, eventually
    from test_monitoring_postgres import add_tree, complete, prepare, put
    from test_selector_tree import css, part, recipe, tree

    from extraction.schemas.models import FieldObservation
    from sources.schemas.models import SourceSnapshot

    openssl = shutil.which("openssl")
    if not openssl:
        pytest.skip("openssl is required for the disposable HTTPS test server")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=example.org",
            "-addext",
            "subjectAltName=DNS:example.org",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_tls.load_cert_chain(cert, key)
    page = b'<!doctype html><html><body><p id="evidence">Public evidence</p></body></html>'
    requests = []

    async def respond(reader, writer):
        try:
            received = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=3)
            requests.append(received)
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n"
                + f"Content-Length: {len(page)}\r\n\r\n".encode()
                + page
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(respond, "127.0.0.1", 0, ssl=server_tls)
    port = server.sockets[0].getsockname()[1]
    # The child uses the real resolver check, pinned HTTP transport, TLS SNI,
    # and parser. Only this synthetic host's DNS answer and socket route are
    # replaced. No loopback allowances are shipped in application code.
    (tmp_path / "sitecustomize.py").write_text(f"""
import ipaddress
import ssl

import httpx
from httpcore._backends.auto import AutoBackend
from monitoring import discovery

connect = AutoBackend.connect_tcp
real_probe = discovery.probe_html

async def resolve(host):
    assert host == "example.org"
    return (ipaddress.ip_address("93.184.216.34"),)

async def test_connect(self, host, port, *args, **kwargs):
    if host == "93.184.216.34" and port == 443:
        host, port = "127.0.0.1", {port}
    return await connect(self, host, port, *args, **kwargs)

async def probe(*args, **kwargs):
    transport = httpx.AsyncHTTPTransport(
        verify=ssl.create_default_context(cafile={str(cert)!r}), trust_env=False,
        limits=httpx.Limits(max_keepalive_connections=0),
    )
    return await real_probe(*args, **kwargs, transport=transport)

discovery.resolve_addresses = resolve
discovery.probe_html = probe
AutoBackend.connect_tcp = test_connect
""")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    monkeypatch.setenv("DCKR_DATABASE_URL", os.environ["COLLECTIONS_TEST_DATABASE_URL"])
    headers, agent_id = await agent(client)
    configure(
        monkeypatch,
        policies={
            "official": {
                "origins": [SITE],
                "autoEnroll": True,
                "agentIds": [agent_id],
            }
        },
        defaultSchedule={"initialSpreadSeconds": 0},
    )
    row = await register(domain)
    await add_tree(client, domain, row.id, None, tree(recipe(part(css("#evidence")))))
    run_id = await submit(client, sourceIds=[row.id])
    assert (await client.post("/monitoring/agents/heartbeat", headers=headers)).status_code == 200
    prefect, restart_prefect = prefect_server
    worker = Service(tmp_path / "worker.log", sys.executable, "-m", "monitoring.worker")

    async def with_status(status):
        return next(
            (item for item in await history(client, row.id) if item["status"] == status), None
        )

    try:
        await prefect.stop()
        await restart_prefect()
        worker.start()
        pending = await eventually(lambda: with_status("pending"))
        assert pending["reason"] == "scheduled" and pending["schedulingFlowRunId"]
        assert requests and b"host: example.org" in requests[0].lower()
        run = await progress(client, run_id)
        assert run["status"] == "completed" and run["items"][0]["sourceState"] == "ACTIVE"
        assert run["items"][0]["diagnostics"]["httpStatus"] == 200
        await worker.stop()

        job = await claim(client, headers)
        assert job["jobId"] == pending["jobId"]
        grant, report = await prepare(client, headers, job, page, "a" * 64)
        await put(grant, page)
        assert (await complete(client, headers, job, report))["status"] == "uploaded"
        worker.start()
        finished = await eventually(lambda: with_status("completed"))
        assert finished["jobId"] == job["jobId"] and finished["processingFlowRunId"]
        assert finished["sourceSnapshotId"] and finished["extractionRunId"]
        assert await domain.count(MonitoringJob, source_id=row.id) == 1
        assert await domain.count(SourceSnapshot, source_id=row.id) == 1
        assert await domain.count(FieldObservation) == 1
        overview = (await client.get("/monitoring/overview", headers=OPERATOR)).json()
        assert overview["lastSuccessfulCheck"] and overview["nextScheduledCheck"]
    except TimeoutError as error:
        log = worker.log.read_text() if worker.log.exists() else ""
        raise AssertionError(log) from error
    finally:
        await worker.stop()
        server.close()
        await server.wait_closed()


async def test_discovery_transaction_can_resume_and_invalid_transition_is_rejected(
    domain, client, monkeypatch
):
    from sources.exceptions import SourceConflict
    from sources.schemas.api import SourceStateChangeRequest

    config = configure(monkeypatch)
    row = await register(domain)
    async with domain.factory.begin() as session:
        with pytest.raises(SourceConflict):
            await SourcesService(session, commit=False).change_state(
                row.id,
                SourceStateChangeRequest(state=State.ACTIVE, expected_state=State.UNDISCOVERED),
            )
    identity = await submit(client, sourceIds=[row.id])

    async def interrupted(*args):
        raise RuntimeError("interrupted after the source transition")

    assert await tick(domain, config, interrupted) == 0
    assert (await progress(client, identity))["items"][0]["sourceState"] == "UNDISCOVERED"
    assert await domain.count(SourceStateHistory, source_id=row.id) == 1
    assert await tick(domain, config) == 1
    assert (await progress(client, identity))["status"] == "completed"
    assert await domain.count(SourceStateHistory, source_id=row.id) == 4


async def test_offline_automatic_jobs_release_capacity_for_other_agents(
    domain, client, monkeypatch
):
    from monitoring.models import MonitoringAgent

    config = configure(monkeypatch, maxActiveJobs=1, defaultSchedule={"initialSpreadSeconds": 0})
    first, second = [await register(domain), await register(domain)]
    await submit(client, sourceIds=[first.id, second.id])
    assert await tick(domain, config) == 2
    first_headers, first_agent = await agent(client, first.id)
    second_headers, _ = await agent(client, second.id)
    assert (
        await client.post("/monitoring/agents/heartbeat", headers=first_headers)
    ).status_code == 200

    async with domain.factory.begin() as session:
        (waiting,) = await MonitoringQueue(session).schedule_due(config=config)
        assert waiting.source_id == first.id

    assert (
        await client.post("/monitoring/agents/heartbeat", headers=second_headers)
    ).status_code == 200
    async with domain.factory.begin() as session:
        offline = utc_now() - timedelta(seconds=config.agent_unavailable_grace_seconds + 1)
        scoped = await session.get(MonitoringAgent, UUID(first_agent))
        scoped.last_seen_at = offline
        previous = await session.get(MonitoringJob, waiting.id)
        previous.available_at = offline
        await session.flush()
        queue = MonitoringQueue(session)
        assert await queue.expire_offline_jobs(config.agent_unavailable_grace_seconds) == 1
        await session.flush()
        assert [job.source_id for job in await queue.schedule_due(config=config)] == [second.id]
        assert previous.status == "cancelled" and previous.error_code == "AGENT_UNAVAILABLE"
