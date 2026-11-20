"""Prefect orchestration. PostgreSQL remains authoritative across flow restarts."""

from datetime import timedelta
from uuid import UUID

from prefect import flow, get_run_logger
from prefect.client.orchestration import get_client
from prefect.deployments import run_deployment
from prefect.exceptions import ObjectNotFound
from prefect.runtime import flow_run
from sqlalchemy import update

from extraction.schemas.common import utc_now
from monitoring.models import SourceCheckRun
from monitoring.processing import MonitoringProcessor
from monitoring.queue import MonitoringQueue
from monitoring.security import MonitoringError
from shared.database import session_factory

PROCESS_DEPLOYMENT = "process-monitoring/monitoring-process"


@flow(name="process-monitoring", timeout_seconds=120, persist_result=False)
async def process_monitoring(job_id: UUID):
    try:
        async with session_factory.begin() as session:
            acquired = await MonitoringProcessor(session).acquire(job_id, flow_run.id)
        if acquired:
            async with session_factory.begin() as session:
                await MonitoringProcessor(session).process(job_id)
    except Exception as error:
        async with session_factory.begin() as session:
            await MonitoringProcessor(session).retry_processing(job_id, flow_run.id)
        # Keep captured text and SQL parameter values out of orchestration logs.
        raise RuntimeError(f"Monitoring processing failed ({type(error).__name__})") from None


async def dispatch(client, job_id, previous):
    if previous:
        try:
            prior = await client.read_flow_run(UUID(previous))
        except ObjectNotFound:
            prior = None
        if prior is not None and prior.state is not None and not prior.state.is_final():
            # A queued run stays queued if no worker is available. A worker
            # crash can leave a run in RUNNING after its DB transaction closes.
            if not prior.state.is_running() or (
                prior.start_time is not None and utc_now() - prior.start_time < timedelta(minutes=5)
            ):
                return False
    run = await run_deployment(
        PROCESS_DEPLOYMENT,
        client=client,
        parameters={"job_id": str(job_id)},
        timeout=0,
        as_subflow=False,
        idempotency_key=f"monitoring:{job_id}:{previous or 'initial'}",
    )
    async with session_factory.begin() as session:
        await session.execute(
            update(SourceCheckRun)
            .where(
                SourceCheckRun.job_id == job_id,
                SourceCheckRun.processing_flow_run_id.is_not_distinct_from(previous),
            )
            .values(processing_flow_run_id=str(run.id))
        )
    return True


@flow(name="schedule-monitoring", retries=2, retry_delay_seconds=10, persist_result=False)
async def schedule_monitoring():
    async with session_factory.begin() as session:
        queue = MonitoringQueue(session)
        cancelled = await queue.cancel_stale()
        expired = await queue.expire_leases()
    async with session_factory.begin() as session:
        queue = MonitoringQueue(session)
        jobs = await queue.schedule_due(flow_run.id)
        ready = await queue.processable()
    dispatch_errors, dispatched = 0, 0
    async with get_client() as client:
        for job_id, prior in ready:
            try:
                dispatched += await dispatch(client, job_id, prior)
            except Exception:
                dispatch_errors += 1
    try:
        async with session_factory.begin() as session:
            cleaned = await MonitoringQueue(session).cleanup_uploads()
    except MonitoringError as error:
        get_run_logger().warning("Upload cleanup deferred (%s)", error.code)
        cleaned = 0
    get_run_logger().info(
        "Scheduled %d checks, cancelled %d, expired %d leases, dispatched %d, cleaned %d uploads",
        len(jobs),
        cancelled,
        expired,
        dispatched,
        cleaned,
    )
    if dispatch_errors:
        raise RuntimeError(f"Could not dispatch {dispatch_errors} monitoring jobs")
