"""Run the single local Prefect worker and reconcile monitoring on every poll."""

import asyncio
import signal
from pathlib import Path

import anyio
from prefect.client.orchestration import get_client
from prefect.exceptions import ObjectNotFound
from prefect.logging import get_logger
from prefect.states import Cancelled, Crashed
from prefect.workers.process import ProcessWorker

from extraction.schemas.common import utc_now
from monitoring.deployments import (
    DEPLOYMENTS,
    IN_FLIGHT,
    POOL,
    PROCESS_DEPLOYMENT,
    QUEUES,
    SCHEDULER_DEPLOYMENT,
    UNFINISHED,
    WORKER,
    needs_migration,
    register,
    run_filters,
)
from monitoring.flows import dispatch
from monitoring.queue import MonitoringQueue
from shared.database import session_factory

POLL_SECONDS = 5
SCHEDULER_SECONDS = 60
DISPATCH_BATCH = 50
logger = get_logger("burbot.monitoring")


def local_process_exists(run):
    """Match the run's identity in its local Process worker subprocess group."""
    pid = run.infrastructure_pid
    if not pid:
        return False
    if not pid.isascii() or not pid.isdecimal():
        return True  # Unrecognized infrastructure. Leave it for an operator.
    proc = Path("/proc")
    if not proc.is_dir():
        return True
    identity = f"PREFECT__FLOW_RUN_ID={run.id}".encode()
    for process in proc.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            state, _, group, *_ = (process / "stat").read_text().rsplit(")", 1)[1].split()
            if state in {"Z", "X", "x"} or (group != pid and process.name != pid):
                continue
            if identity in (process / "environ").read_bytes().split(b"\0"):
                return True
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, ValueError, IndexError):
            return True  # Insufficient evidence to recover this run.
    return False


async def recover_orphans(client, worker, deployment_ids, queue_ids):
    if not worker.is_setup:
        return
    runs = await client.read_flow_runs(
        **run_filters(deployment_ids, IN_FLIGHT, queue_ids=queue_ids)
    )
    for run in runs:
        if run.work_queue_id not in queue_ids or run.labels.get("prefect.worker.name") not in (
            None,
            worker.name,
        ):
            continue
        # The sole Process worker borrows capacity before proposing Pending and
        # holds it through submission and child exit. Container restart ends all
        # children of the previous worker. An old timestamp proves neither.
        if run.id in worker.limiter.statistics().borrowers:
            continue
        try:
            current = await client.read_flow_run(run.id)
        except ObjectNotFound:
            continue
        if (
            current.state is None
            or current.state_id != run.state_id
            or run.id in worker.limiter.statistics().borrowers
            or local_process_exists(current)
        ):
            continue
        message = "Monitoring Process worker no longer owns a live execution."
        state = (
            Cancelled(message=message)
            if current.state.is_cancelling()
            else Crashed(message=message)
        )
        result = await client.set_flow_run_state(run.id, state)
        logger.info(
            "orphan_flow_run_id=%s previous_state=%s recovery_status=%s",
            run.id,
            current.state.name,
            result.status.value,
        )


async def schedule_tick(client, deployment_id, queue_id, minute):
    """Enqueue at most one clock run, with no catch-up after a busy or offline minute."""
    unfinished = await client.read_flow_runs(
        **run_filters([deployment_id], UNFINISHED, queue_ids=[queue_id]), limit=1
    )
    if unfinished:
        return
    await client.create_flow_run_from_deployment(
        deployment_id, idempotency_key=f"monitoring-scheduler:{deployment_id}:{minute}"
    )


async def dispatch_batch(client, deployment_id, cursor):
    async with session_factory() as session:
        rows = await MonitoringQueue(session).processable(DISPATCH_BATCH, after=cursor)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + POLL_SECONDS
    for available_at, job_id in rows:
        try:
            await dispatch(client, deployment_id, job_id, logger)
        except Exception:
            # dispatch already logged the error category. Keep scanning other jobs.
            pass
        if loop.time() >= deadline:
            return available_at, job_id
    return tuple(rows[-1]) if len(rows) == DISPATCH_BATCH else None


async def coordinate(worker, deployment_name):
    cursor, last_minute = None, None
    queue_name = DEPLOYMENTS[deployment_name][1]
    async with get_client() as client:
        while True:
            try:
                async with asyncio.timeout(15):
                    pool = await client.read_work_pool(POOL)
                    deployment = await client.read_deployment_by_name(deployment_name)
                    queue = await client.read_work_queue_by_name(queue_name, work_pool_name=POOL)
                    managed = not needs_migration(deployment_name, deployment)
                    if managed:
                        await recover_orphans(client, worker, [deployment.id], [queue.id])
                    runnable = managed and not (
                        pool.is_paused or deployment.paused or queue.is_paused
                    )
                    if runnable and deployment_name == SCHEDULER_DEPLOYMENT:
                        minute = int(utc_now().timestamp()) // SCHEDULER_SECONDS
                        if minute != last_minute:
                            await schedule_tick(client, deployment.id, queue.id, minute)
                            last_minute = minute
                if runnable and deployment_name == PROCESS_DEPLOYMENT:
                    cursor = await dispatch_batch(client, deployment.id, cursor)
            except Exception as error:
                logger.warning(
                    "deployment=%s reconciliation_status=retry error_category=%s",
                    deployment_name,
                    type(error).__name__,
                )
            await asyncio.sleep(POLL_SECONDS)


async def main():
    async with get_client() as client:
        # This creates missing resources only. Existing deployment updates are
        # explicit, because Prefect can discard scheduled runs on registration.
        await register(client)

    worker = ProcessWorker(
        work_pool_name=POOL,
        work_queues=list(QUEUES),
        name=WORKER,
        limit=sum(QUEUES.values()),
        create_pool_if_not_found=False,
    )
    with anyio.open_signal_receiver(signal.SIGINT, signal.SIGTERM) as signals:
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(worker.start)
            for name in DEPLOYMENTS:
                tasks.start_soon(coordinate, worker, name)
            async for _ in signals:
                tasks.cancel_scope.cancel()
                break


if __name__ == "__main__":
    anyio.run(main)
