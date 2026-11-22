"""Exercise the monitoring queues using Prefect's API, Process worker and Firefox protocol."""

import asyncio
import logging
import os
import signal
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_collections_postgres import domain as domain
from test_collections_postgres import migrate
from test_monitoring_postgres import (
    add_tree,
    agent,
    claim,
    complete,
    enqueue,
    history,
    prepare,
    put,
    source,
)
from test_monitoring_postgres import client as client
from test_monitoring_postgres import minio as minio
from test_selector_tree import css, part, recipe, tree

from extraction.schemas.common import utc_now
from extraction.schemas.models import ExtractionRun, FieldObservation
from monitoring.models import MonitoringJob, SourceCheckRun
from sources.schemas.models import SourceCheckSchedule, SourceSnapshot
from tasks.schemas.models import Workflow

pytestmark = pytest.mark.asyncio
ROOT = Path(__file__).resolve().parents[1]


async def eventually(read, *, timeout=35):
    async with asyncio.timeout(timeout):
        while True:
            if value := await read():
                return value
            await asyncio.sleep(0.15)


class Service:
    def __init__(self, log, *command):
        self.log = log
        self.command = command
        self.process = None

    def start(self):
        with self.log.open("ab") as output:
            self.process = subprocess.Popen(
                self.command, stdout=output, stderr=subprocess.STDOUT, cwd=ROOT
            )

    async def stop(self, *, kill=False):
        if self.process is None or self.process.poll() is not None:
            return
        if kill:
            self.process.kill()
        else:
            self.process.terminate()
        try:
            await asyncio.to_thread(self.process.wait, 12)
        except subprocess.TimeoutExpired:
            self.process.kill()
            await asyncio.to_thread(self.process.wait, 5)


@pytest_asyncio.fixture
async def prefect_server(tmp_path, monkeypatch, unused_tcp_port):
    pytest.importorskip("prefect")
    from prefect.settings import PREFECT_API_URL, temporary_settings

    url = f"http://127.0.0.1:{unused_tcp_port}/api"
    monkeypatch.setenv("PREFECT_API_URL", url)
    monkeypatch.setenv("PREFECT_HOME", str(tmp_path / "prefect"))
    monkeypatch.setenv("PREFECT_SERVER_ANALYTICS_ENABLED", "false")
    monkeypatch.setenv("PREFECT_WORKER_QUERY_SECONDS", "1")
    monkeypatch.setenv("PREFECT_WORKER_PREFETCH_SECONDS", "0")
    monkeypatch.setenv("DCKR_DATABASE_URL", "postgresql+asyncpg://test@localhost/test")
    service = Service(
        tmp_path / "prefect.log",
        str(Path(sys.executable).with_name("prefect")),
        "server",
        "start",
        "--host",
        "127.0.0.1",
        "--port",
        str(unused_tcp_port),
    )

    async def start():
        service.start()

        async def ready():
            assert service.process.poll() is None, service.log.read_text()
            async with httpx.AsyncClient() as http:
                try:
                    response = await http.get(f"{url}/health", timeout=1)
                except httpx.TransportError:
                    return False
            return response.is_success

        await eventually(ready)

    try:
        await start()
        with temporary_settings({PREFECT_API_URL: url}):
            yield service, start
    finally:
        await service.stop()


@pytest_asyncio.fixture
async def database(monkeypatch):
    """Give the real Process worker its own migrated database via the normal DSN."""
    url = os.getenv("COLLECTIONS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set COLLECTIONS_TEST_DATABASE_URL to run PostgreSQL worker tests")
    name = f"monitoring_test_{uuid4().hex}"
    isolated_url = make_url(url).set(database=name).render_as_string(hide_password=False)
    monkeypatch.setenv("HOST_DATABASE_URL", isolated_url)
    monkeypatch.setenv("COLLECTIONS_TEST_DATABASE_URL", isolated_url)
    admin = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_async_engine(isolated_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(lambda conn: migrate(conn, "public", "head"))
        yield engine, async_sessionmaker(engine, expire_on_commit=False, autoflush=False), "public"
    finally:
        await engine.dispose()
        async with admin.connect() as connection:
            await connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        await admin.dispose()


async def test_scheduler_coalesces_and_processing_bypasses_legacy_backlog(prefect_server):
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import WorkPoolUpdate
    from prefect.states import Completed, Running, Scheduled, StateType
    from prefect.workers.process import ProcessWorker

    from monitoring.deployments import (
        POOL,
        PROCESS_DEPLOYMENT,
        PROCESS_QUEUE,
        QUEUES,
        SCHEDULER_DEPLOYMENT,
        SCHEDULER_QUEUE,
        UNFINISHED,
        WORKER,
        register,
        run_filters,
    )
    from monitoring.worker import recover_orphans, schedule_tick

    async with get_client() as api:
        await register(api)
        scheduler = await api.read_deployment_by_name(SCHEDULER_DEPLOYMENT)
        processing = await api.read_deployment_by_name(PROCESS_DEPLOYMENT)
        queue = await api.read_work_queue_by_name(SCHEDULER_QUEUE, work_pool_name=POOL)
        processing_queue = await api.read_work_queue_by_name(PROCESS_QUEUE, work_pool_name=POOL)
        assert processing_queue.priority < queue.priority
        assert queue.concurrency_limit == 1 and processing_queue.concurrency_limit == 4
        assert not scheduler.schedules and scheduler.global_concurrency_limit is None

        await schedule_tick(api, scheduler.id, queue.id, minute=100)
        live_filter = run_filters([scheduler.id], UNFINISHED, queue_ids=[queue.id])
        (scheduler_run,) = await api.read_flow_runs(**live_filter)
        for minute in range(101, 104):
            await schedule_tick(api, scheduler.id, queue.id, minute)
        assert await api.count_flow_runs(**live_filter) == 1

        await api.set_flow_run_state(scheduler_run.id, Running(), force=True)
        process_run = await api.create_flow_run_from_deployment(
            processing.id, parameters={"job_id": str(uuid4())}, state=Scheduled()
        )
        await api.update_work_pool(POOL, WorkPoolUpdate(concurrency_limit=1))
        assert not await api.get_scheduled_flow_runs_for_work_pool(POOL, list(QUEUES))
        assert (await api.read_flow_run(process_run.id)).state.is_scheduled()
        worker = ProcessWorker(work_pool_name=POOL, work_queues=list(QUEUES), limit=5, name=WORKER)
        async with worker:
            worker.limiter.acquire_on_behalf_of_nowait(scheduler_run.id)
            for minute in range(104, 109):
                await schedule_tick(api, scheduler.id, queue.id, minute)
                await recover_orphans(api, worker, [scheduler.id], [queue.id])
            assert (await api.read_flow_run(scheduler_run.id)).state.is_running()
            assert await api.count_flow_runs(**live_filter) == 1
            worker.limiter.release_on_behalf_of(scheduler_run.id)
            await recover_orphans(api, worker, [scheduler.id], [queue.id])
            assert (await api.read_flow_run(scheduler_run.id)).state.is_crashed()
        await api.update_work_pool(POOL, WorkPoolUpdate(concurrency_limit=None))

        # Legacy runs keep their original queue after a deployment moves.
        for start in range(0, 240, 80):
            await api.request(
                "POST",
                f"/deployments/{scheduler.id}/create_flow_run/bulk",
                json=[
                    {"work_queue_name": "default", "idempotency_key": f"legacy:{n}"}
                    for n in range(start, start + 80)
                ],
            )
        await schedule_tick(api, scheduler.id, queue.id, minute=109)
        waiting = await api.get_scheduled_flow_runs_for_work_pool(POOL, list(QUEUES))
        assert len(waiting) == 2 and waiting[0].flow_run.id == process_run.id
        assert (
            await api.count_flow_runs(**run_filters([scheduler.id], [StateType.SCHEDULED])) == 241
        )

        (new_scheduler_run,) = await api.read_flow_runs(**live_filter)
        await api.set_flow_run_state(new_scheduler_run.id, Completed(), force=True)
        await schedule_tick(api, scheduler.id, queue.id, minute=109)
        assert await api.count_flow_runs(**live_filter) == 0
        await schedule_tick(api, scheduler.id, queue.id, minute=110)
        assert await api.count_flow_runs(**live_filter) == 1


async def test_migrate_preserves_pauses_ids_and_history(prefect_server):
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.actions import DeploymentUpdate, WorkPoolCreate
    from prefect.flows import EntrypointType
    from prefect.states import Completed, Pending, StateType
    from prefect.workers.process import ProcessWorker

    from monitoring.deployments import (
        POOL,
        SCHEDULER_DEPLOYMENT,
        SCHEDULER_QUEUE,
        register,
        run_filters,
    )
    from monitoring.flows import schedule_monitoring
    from monitoring.recovery import cancel_scheduler_runs, reconcile_orphan

    async with get_client() as api:
        await api.create_work_pool(
            WorkPoolCreate(
                name=POOL,
                type="process",
                base_job_template=ProcessWorker.get_default_base_job_template(),
            )
        )
        legacy = await schedule_monitoring.ato_deployment(
            name="monitoring-scheduler",
            interval=60,
            concurrency_limit=1,
            paused=True,
            entrypoint_type=EntrypointType.MODULE_PATH,
            work_pool_name=POOL,
        )
        legacy_id = await legacy.aapply()
        configuration = await api.read_deployment(legacy_id)
        (legacy_schedule,) = configuration.schedules
        stranded = await api.create_flow_run_from_deployment(legacy_id)
        terminal = await api.create_flow_run_from_deployment(legacy_id, state=Completed())
        assert (await api.set_flow_run_state(stranded.id, Pending())).state.is_pending()
        collision = await api.create_flow_run_from_deployment(legacy_id)
        assert (await api.set_flow_run_state(collision.id, Pending())).state.name == (
            "AwaitingConcurrencySlot"
        )
        assert (await api.read_deployment(legacy_id)).global_concurrency_limit.active_slots == 1
        with pytest.raises(RuntimeError, match="in-flight"):
            await register(api, migrate=True)
        with pytest.raises(ValueError, match="not an unstarted legacy scheduler run"):
            await cancel_scheduler_runs(api, [stranded.id])
        await reconcile_orphan(api, stranded.id)
        assert (await api.read_deployment(legacy_id)).global_concurrency_limit.active_slots == 0
        now = utc_now()
        await api.request(
            "POST",
            f"/deployments/{legacy_id}/schedule",
            json={
                "start_time": (now + timedelta(minutes=2)).isoformat(),
                "end_time": (now + timedelta(minutes=4)).isoformat(),
                "max_runs": 1,
            },
        )
        (obsolete,) = [
            run
            for run in await api.read_flow_runs(**run_filters([legacy_id], [StateType.SCHEDULED]))
            if run.auto_scheduled
        ]
        with pytest.raises(RuntimeError, match="future auto-scheduled"):
            await register(api, migrate=True)
        await cancel_scheduler_runs(api, [obsolete.id])
        assert (await api.read_flow_run(obsolete.id)).state.is_cancelled()

        await register(api, migrate=True)
        migrated = await api.read_deployment_by_name(SCHEDULER_DEPLOYMENT)
        assert migrated.id == legacy_id and migrated.paused
        assert migrated.work_queue_name == SCHEDULER_QUEUE
        assert migrated.global_concurrency_limit is None
        (schedule,) = migrated.schedules
        assert not schedule.active and schedule.id == legacy_schedule.id
        assert (await api.read_flow_run(terminal.id)).state.is_completed()
        assert (await api.read_flow_run(stranded.id)).state.is_crashed()
        assert (await api.read_flow_run(collision.id)).state.name == "AwaitingConcurrencySlot"
        await api.update_deployment(legacy_id, DeploymentUpdate(tags=["operator-configured"]))
        await register(api)
        await register(api, migrate=True)
        repeated = await api.read_deployment(legacy_id)
        assert repeated.tags == ["operator-configured"] and repeated.paused
        assert repeated.schedules[0].id == legacy_schedule.id


async def test_dispatch_replays_a_lost_response(
    prefect_server, domain, client, monkeypatch, caplog
):
    from prefect.client.orchestration import get_client
    from prefect.states import StateType

    from monitoring import flows
    from monitoring.deployments import PROCESS_DEPLOYMENT, register, run_filters

    monkeypatch.setattr(flows, "session_factory", domain.factory)
    source_row = await source(domain, client)
    job_id = UUID(await enqueue(client, source_row.id))
    async with domain.factory.begin() as session:
        job = await session.get(MonitoringJob, job_id)
        job.status = "uploaded"

    async with get_client() as api:
        await register(api)
        deployment = await api.read_deployment_by_name(PROCESS_DEPLOYMENT)

        class LostResponse:
            async def create_flow_run_from_deployment(self, *args, **kwargs):
                await api.create_flow_run_from_deployment(*args, **kwargs)
                raise ConnectionError("sensitive test diagnostic")

        with pytest.raises(ConnectionError):
            await flows.dispatch(LostResponse(), deployment.id, job_id, logging.getLogger(__name__))
        assert "dispatch_status=retry" in caplog.text
        assert "sensitive test diagnostic" not in caplog.text
        async with domain.factory() as session:
            assert (await session.get(SourceCheckRun, job_id)).processing_flow_run_id is None

        for _ in range(3):
            await flows.dispatch(api, deployment.id, job_id, logging.getLogger(__name__))
        (run,) = await api.read_flow_runs(**run_filters([deployment.id], [StateType.SCHEDULED]))
        async with domain.factory() as session:
            assert (await session.get(SourceCheckRun, job_id)).processing_flow_run_id == str(run.id)


@pytest.mark.parametrize("crash", [False, True])
async def test_uploaded_job_finishes_automatically(
    crash, prefect_server, domain, client, minio, tmp_path, monkeypatch
):
    from prefect.client.orchestration import get_client
    from prefect.states import Pending, Submitting

    from monitoring.deployments import PROCESS_DEPLOYMENT, SCHEDULER_DEPLOYMENT

    # The Prefect fixture can run without PostgreSQL. Give the worker the real
    # isolated DSN after both fixtures have finished configuring the environment.
    monkeypatch.setenv("DCKR_DATABASE_URL", os.environ["COLLECTIONS_TEST_DATABASE_URL"])
    prefect, start_prefect = prefect_server
    worker = Service(tmp_path / "worker.log", sys.executable, "-m", "monitoring.worker")
    row = await source(domain, client)
    await add_tree(client, domain, row.id, None, tree(recipe(part(css("#evidence")))))
    headers, _ = await agent(client, row.id)
    async with domain.factory.begin() as session:
        schedule = await session.get(SourceCheckSchedule, row.id)
        schedule.interval_seconds = 3600

    async def check_with_status(status):
        checks = await history(client, row.id)
        return next((check for check in checks if check["status"] == status), None)

    try:
        worker.start()
        planned = await eventually(lambda: check_with_status("pending"))
        assert planned["schedulingFlowRunId"]
        identity = UUID(planned["jobId"])
        if crash:
            await worker.stop()
        job = await claim(client, headers)
        assert job["jobId"] == str(identity)
        html = b'<p id="evidence">Example evidence</p>'
        grant, data = await prepare(client, headers, job, html, "a" * 64)
        await put(grant, html)
        if not crash:
            await prefect.stop()
        assert (await complete(client, headers, job, data))["status"] == "uploaded"
        if not crash:
            await start_prefect()

        async with get_client() as api:
            scheduler = await api.read_deployment_by_name(SCHEDULER_DEPLOYMENT)
            if crash:
                await api.pause_deployment(scheduler.id)
                processing = await api.read_deployment_by_name(PROCESS_DEPLOYMENT)
                abandoned = await api.create_flow_run_from_deployment(
                    processing.id, parameters={"job_id": str(identity)}
                )
                await api.set_flow_run_state(abandoned.id, Pending())
                assert (
                    await api.set_flow_run_state(abandoned.id, Submitting())
                ).state.name == "Submitting"
                async with domain.factory.begin() as session:
                    check = await session.get(SourceCheckRun, identity)
                    check.processing_flow_run_id = str(abandoned.id)
                    session.add(Workflow(source_id=row.id, source_snapshot_id=0))

                await prefect.stop()
                await start_prefect()
                assert (await api.read_flow_run(abandoned.id)).state.name == "Submitting"
                assert (await check_with_status("uploaded"))["jobId"] == str(identity)

                async with domain.factory.begin() as session:
                    await session.scalar(select(Workflow).with_for_update())
                    worker.start()
                    acquired = await eventually(lambda: check_with_status("processing"))
                    interrupted_id = UUID(acquired["processingFlowRunId"])
                    assert interrupted_id != abandoned.id
                    assert (await api.read_flow_run(abandoned.id)).state.is_crashed()

                    async def running():
                        run = await api.read_flow_run(interrupted_id)
                        return run if run.infrastructure_pid and run.state.is_running() else None

                    running_run = await eventually(running)
                    assert acquired["sourceSnapshotId"] and acquired["extractionRunId"]
                    # The workflow lock keeps the live subprocess between acquisition
                    # and its evidence transaction while the worker is terminated.
                    await worker.stop(kill=True)
                    os.killpg(int(running_run.infrastructure_pid), signal.SIGKILL)
                assert (await api.read_flow_run(interrupted_id)).state.is_running()
                worker.start()

            finished = await eventually(lambda: check_with_status("completed"))
            assert finished["jobId"] == str(identity)
            run = await api.read_flow_run(UUID(finished["processingFlowRunId"]))
            assert run.parameters["job_id"] == str(identity)
            if crash:
                assert (await api.read_flow_run(interrupted_id)).state.is_crashed()
                assert finished["sourceSnapshotId"] == acquired["sourceSnapshotId"]
                assert finished["extractionRunId"] == acquired["extractionRunId"]
                assert (await api.read_deployment(scheduler.id)).paused
        assert await domain.count(MonitoringJob, source_id=row.id) == 1
        assert await domain.count(SourceSnapshot, source_id=row.id) == 1
        assert (
            await domain.count(ExtractionRun, source_snapshot_id=finished["sourceSnapshotId"]) == 1
        )
        assert await domain.count(FieldObservation) == 1
    except TimeoutError as error:
        raise AssertionError(worker.log.read_text() if worker.log.exists() else "") from error
    finally:
        await worker.stop()
