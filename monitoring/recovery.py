"""Inspect monitoring orchestration and cancel explicitly reviewed legacy scheduler runs."""

import argparse
import asyncio
import json
import sys
from collections import Counter
from uuid import UUID

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import DeploymentUpdate
from prefect.client.schemas.sorting import FlowRunSort
from prefect.exceptions import ObjectNotFound
from prefect.states import Cancelled, Cancelling, Crashed
from sqlalchemy import func, select

from monitoring.deployments import (
    DEPLOYMENTS,
    IN_FLIGHT,
    SCHEDULER_DEPLOYMENT,
    SCHEDULER_QUEUE,
    UNFINISHED,
    has_future_auto_runs,
    needs_migration,
    run_filters,
)
from monitoring.models import PROCESSABLE, MonitoringJob, SourceCheckRun
from shared.database import session_factory


def obsolete_scheduler_run(run, deployment_id):
    return (
        run.deployment_id == deployment_id
        and run.work_queue_name != SCHEDULER_QUEUE
        and run.auto_scheduled
        and run.state is not None
        and run.state.is_scheduled()
        and run.start_time is None
        and run.infrastructure_pid is None
        and run.run_count == 0
    )


async def report(client, *, include_runs, job_id):
    output = {}
    for name in DEPLOYMENTS:
        deployment = await client.read_deployment_by_name(name)
        filters = run_filters([deployment.id], UNFINISHED)
        counts = Counter()
        details = []
        oldest = None
        offset = 0
        while True:
            runs = await client.read_flow_runs(
                **filters, sort=FlowRunSort.EXPECTED_START_TIME_ASC, limit=200, offset=offset
            )
            if not runs:
                break
            for run in runs:
                counts[f"{run.work_queue_name or 'unassigned'}/{run.state.name}"] += 1
                if run.state.is_scheduled() and oldest is None:
                    oldest = run.expected_start_time
                if include_runs:
                    details.append(
                        {
                            "id": run.id,
                            "state": run.state.name,
                            "queue": run.work_queue_name,
                            "expected_start": run.expected_start_time,
                            "started": run.start_time,
                            "worker": run.labels.get("prefect.worker.name"),
                            "pid": run.infrastructure_pid,
                            "obsolete_scheduler_candidate": (
                                name == SCHEDULER_DEPLOYMENT
                                and obsolete_scheduler_run(run, deployment.id)
                            ),
                        }
                    )
            offset += len(runs)
        slots = deployment.global_concurrency_limit
        output[name] = {
            "id": deployment.id,
            "paused": deployment.paused,
            "queue": deployment.work_queue_name,
            "unfinished_by_queue_and_state": dict(counts),
            "oldest_scheduled": oldest,
            "deployment_concurrency": (
                {"limit": slots.limit, "active_slots": slots.active_slots} if slots else None
            ),
        }
        if include_runs:
            output[name]["runs"] = details
        if deployment.work_queue_id is not None:
            try:
                queue = await client.read_work_queue_concurrency_status(deployment.work_queue_id)
            except ObjectNotFound:
                pass  # Older servers expose only deployment concurrency.
            else:
                output[name]["queue_concurrency"] = {
                    "limit": queue.concurrency_limit,
                    "active_slots": queue.active_slots,
                }

    async with session_factory() as session:
        output["processable_jobs"] = [
            dict(row)
            for row in (
                await session.execute(
                    select(
                        MonitoringJob.status,
                        func.count().label("count"),
                        func.min(MonitoringJob.available_at).label("oldest_available_at"),
                    )
                    .where(MonitoringJob.status.in_(PROCESSABLE))
                    .group_by(MonitoringJob.status)
                )
            ).mappings()
        ]
        if job_id:
            row = (
                (
                    await session.execute(
                        select(
                            MonitoringJob.id,
                            MonitoringJob.status,
                            MonitoringJob.processing_attempts,
                            MonitoringJob.error_code,
                            MonitoringJob.source_snapshot_id,
                            MonitoringJob.extraction_run_id,
                            SourceCheckRun.processing_flow_run_id,
                        )
                        .join(SourceCheckRun, SourceCheckRun.job_id == MonitoringJob.id)
                        .where(MonitoringJob.id == job_id)
                    )
                )
                .mappings()
                .one_or_none()
            )
            output["job"] = dict(row) if row else None
    print(json.dumps(output, default=str, indent=2))


async def cancel_scheduler_runs(client, run_ids):
    deployment = await client.read_deployment_by_name(SCHEDULER_DEPLOYMENT)
    # Validate the entire manifest first, then re-check each state immediately
    # before requesting cancellation. The operator must stop the legacy worker.
    candidates = []
    for run_id in run_ids:
        run = await client.read_flow_run(run_id)
        if not obsolete_scheduler_run(run, deployment.id):
            if run.deployment_id == deployment.id and run.state and run.state.is_cancelled():
                continue
            raise ValueError(f"Run {run_id} is not an unstarted legacy scheduler run")
        candidates.append(run)
    for run in candidates:
        current = await client.read_flow_run(run.id)
        if not obsolete_scheduler_run(current, deployment.id):
            raise ValueError(f"Run {run.id} changed while reconciling the backlog")
        result = await client.set_flow_run_state(
            run.id, Cancelling(message="Reviewed obsolete monitoring scheduler tick.")
        )
        if result.state is None or not result.state.is_cancelled():
            raise RuntimeError(f"Run {run.id} did not reach Cancelled. Inspect its state.")
        print(f"{run.id} Cancelled")


async def reconcile_orphan(client, run_id):
    run = await client.read_flow_run(run_id)
    deployment_ids = set()
    for name in DEPLOYMENTS:
        try:
            deployment_ids.add((await client.read_deployment_by_name(name)).id)
        except ObjectNotFound:
            continue
    if run.deployment_id not in deployment_ids or run.state is None:
        raise ValueError(f"Run {run_id} is outside the monitoring deployments")
    if run.state.type not in IN_FLIGHT:
        raise ValueError(f"Run {run_id} is not in flight")
    message = "Operator confirmed that the monitoring worker and its subprocess stopped."
    state = Cancelled(message=message) if run.state.is_cancelling() else Crashed(message=message)
    result = await client.set_flow_run_state(run.id, state)
    if result.state is None or result.state.type != state.type:
        raise RuntimeError(f"Run {run.id} did not reach {state.name}. Inspect its state.")
    print(f"{run.id} {state.name}")


async def set_scheduler_pause(client, paused):
    deployment = await client.read_deployment_by_name(SCHEDULER_DEPLOYMENT)
    if paused:
        if not deployment.paused:
            if await has_future_auto_runs(client, deployment.id):
                raise RuntimeError("Reconcile future auto-scheduled runs before pausing")
            await client.update_deployment(deployment.id, DeploymentUpdate(paused=True))
    elif needs_migration(SCHEDULER_DEPLOYMENT, deployment):
        raise RuntimeError("Migrate the scheduler deployment before resuming")
    elif deployment.paused:
        await client.resume_deployment(deployment.id)


async def main(args):
    async with get_client() as client:
        if args.command == "status":
            await report(client, include_runs=args.runs, job_id=args.job_id)
        elif args.command == "cancel-scheduler":
            run_ids = dict.fromkeys(UUID(line.strip()) for line in sys.stdin if line.strip())
            await cancel_scheduler_runs(client, run_ids)
        elif args.command == "reconcile-orphan":
            await reconcile_orphan(client, args.run_id)
        else:
            await set_scheduler_pause(client, paused=args.command == "pause-scheduler")


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    status = commands.add_parser("status")
    status.add_argument("--runs", action="store_true", help="Include unfinished run IDs")
    status.add_argument("--job-id", type=UUID)
    commands.add_parser(
        "cancel-scheduler",
        help="After stopping the legacy worker, read reviewed scheduler UUIDs from stdin",
    )
    orphan = commands.add_parser("reconcile-orphan")
    orphan.add_argument("run_id", type=UUID)
    orphan.add_argument(
        "--confirm-stopped",
        required=True,
        action="store_true",
        help="Confirm that the run's worker and subprocess have stopped",
    )
    commands.add_parser("pause-scheduler", help="Pause after disabling the legacy clock")
    commands.add_parser("resume-scheduler", help="Resume the migrated scheduler")
    asyncio.run(main(cli.parse_args()))
