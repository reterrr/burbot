"""Provision monitoring's dedicated queues and deployments through Prefect."""

import argparse
import asyncio

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import DeploymentUpdate, WorkPoolCreate
from prefect.client.schemas.filters import FlowRunFilter, WorkQueueFilter
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound
from prefect.flows import EntrypointType
from prefect.states import StateType
from prefect.workers.process import ProcessWorker

from extraction.schemas.common import utc_now
from monitoring.flows import process_monitoring, schedule_monitoring

POOL = "burbot-monitoring"
WORKER = "burbot-monitoring-worker"
PROCESS_QUEUE = "monitoring-processing"
SCHEDULER_QUEUE = "monitoring-scheduling"
PROCESS_DEPLOYMENT = "process-monitoring/monitoring-process"
SCHEDULER_DEPLOYMENT = "schedule-monitoring/monitoring-scheduler"
QUEUES = {PROCESS_QUEUE: 4, SCHEDULER_QUEUE: 1}
DEPLOYMENTS = {
    PROCESS_DEPLOYMENT: (process_monitoring, PROCESS_QUEUE),
    SCHEDULER_DEPLOYMENT: (schedule_monitoring, SCHEDULER_QUEUE),
}
IN_FLIGHT = (StateType.PENDING, StateType.RUNNING, StateType.CANCELLING)
UNFINISHED = (StateType.SCHEDULED, StateType.PAUSED, *IN_FLIGHT)


def run_filters(deployment_ids, states, *, queue_ids=None, **conditions):
    return {
        "flow_run_filter": FlowRunFilter(
            deployment_id={"any_": deployment_ids}, state={"type": {"any_": states}}, **conditions
        ),
        "work_queue_filter": WorkQueueFilter(id={"any_": queue_ids}) if queue_ids else None,
    }


async def ensure_queues(client):
    try:
        pool = await client.read_work_pool(POOL)
    except ObjectNotFound:
        try:
            pool = await client.create_work_pool(
                WorkPoolCreate(
                    name=POOL,
                    type="process",
                    base_job_template=ProcessWorker.get_default_base_job_template(),
                )
            )
        except ObjectAlreadyExists:
            pool = await client.read_work_pool(POOL)
    if pool.type != "process":
        raise RuntimeError(f"Work pool {POOL} must use the Process worker type")
    for priority, (name, limit) in enumerate(QUEUES.items(), start=1):
        try:
            await client.read_work_queue_by_name(name, work_pool_name=POOL)
        except ObjectNotFound:
            try:
                await client.create_work_queue(
                    name, work_pool_name=POOL, concurrency_limit=limit, priority=priority
                )
            except ObjectAlreadyExists:
                pass


def needs_migration(name, deployment):
    return (
        deployment.work_pool_name != POOL
        or deployment.work_queue_name != DEPLOYMENTS[name][1]
        or deployment.global_concurrency_limit is not None
        or (name == SCHEDULER_DEPLOYMENT and any(s.active for s in deployment.schedules))
    )


async def check_migration(client, name, deployment):
    if name == SCHEDULER_DEPLOYMENT and not deployment.paused:
        raise RuntimeError("Pause the legacy scheduler deployment before migrating")
    if await client.count_flow_runs(**run_filters([deployment.id], IN_FLIGHT)):
        raise RuntimeError(f"Drain or reconcile in-flight runs of {name} before migrating")
    if await has_future_auto_runs(client, deployment.id):
        raise RuntimeError(f"Reconcile future auto-scheduled runs of {name} before migrating")


async def has_future_auto_runs(client, deployment_id):
    # Prefect PATCH endpoints remove future, never-started, auto-scheduled runs.
    # Require these to have been explicitly reconciled before mutating the deployment.
    filters = run_filters(
        [deployment_id], [StateType.SCHEDULED], next_scheduled_start_time={"after_": utc_now()}
    )
    offset = 0
    while runs := await client.read_flow_runs(**filters, limit=200, offset=offset):
        if any(run.auto_scheduled for run in runs):
            return True
        offset += len(runs)
    return False


async def register(client, *, migrate=False):
    existing = {}
    for name in DEPLOYMENTS:
        try:
            existing[name] = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            continue
        if needs_migration(name, existing[name]):
            if not migrate:
                raise RuntimeError(
                    f"Legacy deployment {name} needs migration. See docs/monitoring.md."
                )
            await check_migration(client, name, existing[name])

    await ensure_queues(client)
    for name, (flow, queue) in DEPLOYMENTS.items():
        deployment = existing.get(name)
        if deployment is None:
            runner = await flow.ato_deployment(
                name=name.split("/")[1],
                entrypoint_type=EntrypointType.MODULE_PATH,
                work_pool_name=POOL,
                work_queue_name=queue,
            )
            await runner.aapply()
        elif needs_migration(name, deployment):
            if name == SCHEDULER_DEPLOYMENT:
                for schedule in deployment.schedules:
                    if schedule.active:
                        await client.update_deployment_schedule(
                            deployment.id, schedule.id, active=False
                        )
            await client.update_deployment(
                deployment.id,
                DeploymentUpdate(
                    work_pool_name=POOL,
                    work_queue_name=queue,
                    concurrency_limit=None,
                    concurrency_options=None,
                ),
            )


async def main(migrate):
    async with get_client() as client:
        await register(client, migrate=migrate)
        for name in DEPLOYMENTS:
            deployment = await client.read_deployment_by_name(name)
            print(f"{name} ({deployment.id}) queue={deployment.work_queue_name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--migrate", action="store_true", help="Move drained legacy deployments")
    asyncio.run(main(parser.parse_args().migrate))
