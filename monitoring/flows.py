"""Prefect flows and the dispatcher backed by the PostgreSQL monitoring queue."""

import asyncio
import logging
from contextlib import suppress
from uuid import UUID

from prefect import flow, get_run_logger
from prefect.exceptions import ObjectNotFound
from prefect.runtime import flow_run
from sqlalchemy import func, select

from extraction.schemas.common import utc_now
from monitoring.enrollment import MonitoringEnrollmentService
from monitoring.models import PROCESSABLE, MonitoringJob, SourceCheckRun
from monitoring.onboarding import ONBOARDING_TICK_SECONDS, run_onboarding_batch
from monitoring.onboarding_config import onboarding_config
from monitoring.processing import MonitoringProcessor
from monitoring.queue import SCHEDULING_LOCK, MonitoringQueue
from monitoring.security import MonitoringError
from shared.database import session_factory

DISPATCH_TIMEOUT = 10
PROCESSING_TIMEOUT = 120


def log_job(logger, level, job_id, processing_run_id, retry_count, **fields):
    logger.log(
        level,
        "monitoring_job_id=%s processing_flow_run_id=%s retry_count=%s %s",
        job_id,
        processing_run_id,
        retry_count,
        " ".join(f"{name}={value}" for name, value in fields.items()),
    )


@flow(name="process-monitoring", retries=0, persist_result=False)
async def process_monitoring(job_id: UUID):
    logger = get_run_logger()
    processing_run_id = flow_run.id
    retry_count = None
    try:
        async with asyncio.timeout(PROCESSING_TIMEOUT):
            async with session_factory.begin() as session:
                retry_count = await session.scalar(
                    select(MonitoringJob.processing_attempts).where(MonitoringJob.id == job_id)
                )
                acquired = await MonitoringProcessor(session).acquire(
                    job_id, processing_run_id, require_dispatch=True
                )
            completed = False
            if acquired:
                async with session_factory.begin() as session:
                    completed = await MonitoringProcessor(session).process(
                        job_id, expected_flow_id=processing_run_id
                    )
    except Exception as error:
        try:
            async with asyncio.timeout(DISPATCH_TIMEOUT), session_factory.begin() as session:
                retry_count = await MonitoringProcessor(session).retry_processing(
                    job_id, processing_run_id, require_dispatch=True
                )
        except Exception as retry_error:
            log_job(
                logger,
                logging.WARNING,
                job_id,
                processing_run_id,
                retry_count,
                processing_status="retry_record_failed",
                error_category=type(retry_error).__name__,
            )
        log_job(
            logger,
            logging.WARNING,
            job_id,
            processing_run_id,
            retry_count,
            processing_status="failed",
            error_category=type(error).__name__,
        )
        # Exceptions from extraction and SQL may include captured text.
        raise RuntimeError(f"Monitoring processing failed ({type(error).__name__})") from None
    log_job(
        logger,
        logging.INFO,
        job_id,
        processing_run_id,
        retry_count,
        processing_status="completed" if completed else "skipped",
    )


async def dispatch(client, deployment_id, job_id, logger):
    """Serialize assignment with processing and replay uncertain Prefect creates."""
    scheduler_run_id = processing_run_id = retry_count = None
    try:
        async with asyncio.timeout(DISPATCH_TIMEOUT), session_factory.begin() as session:
            row = (
                await session.execute(
                    select(MonitoringJob.processing_attempts, SourceCheckRun)
                    .join(SourceCheckRun, SourceCheckRun.job_id == MonitoringJob.id)
                    .where(
                        MonitoringJob.id == job_id,
                        MonitoringJob.status.in_(PROCESSABLE),
                        MonitoringJob.available_at <= utc_now(),
                    )
                    .with_for_update(of=MonitoringJob, skip_locked=True)
                )
            ).one_or_none()
            if row is None:
                return
            retry_count, check = row
            scheduler_run_id = check.scheduling_flow_run_id
            processing_run_id = previous = check.processing_flow_run_id
            prior_id = prior = None
            if previous:
                with suppress(ValueError):
                    prior_id = UUID(previous)
            if prior_id is not None:
                with suppress(ObjectNotFound):
                    prior = await client.read_flow_run(prior_id)
            if (
                prior is not None
                and prior.deployment_id == deployment_id
                and (prior.state is None or not prior.state.is_final())
            ):
                log_job(
                    logger,
                    logging.DEBUG,
                    job_id,
                    previous,
                    retry_count,
                    scheduler_run_id=scheduler_run_id,
                    dispatch_status="existing",
                )
                return
            run = await client.create_flow_run_from_deployment(
                deployment_id,
                parameters={"job_id": str(job_id)},
                idempotency_key=f"monitoring:{job_id}:{previous or 'initial'}",
            )
            check.processing_flow_run_id = processing_run_id = str(run.id)
    except Exception as error:
        log_job(
            logger,
            logging.WARNING,
            job_id,
            processing_run_id,
            retry_count,
            scheduler_run_id=scheduler_run_id,
            dispatch_status="retry",
            error_category=type(error).__name__,
        )
        raise
    log_job(
        logger,
        logging.INFO,
        job_id,
        processing_run_id,
        retry_count,
        scheduler_run_id=scheduler_run_id,
        dispatch_status="linked",
    )
    return True


@flow(name="schedule-monitoring", retries=0, timeout_seconds=300, persist_result=False)
async def schedule_monitoring():
    logger = get_run_logger()
    scheduler_run_id = flow_run.id
    config = None
    onboarded = 0
    try:
        config = onboarding_config()
        if config.mode == "strict" and config.policies:
            async with asyncio.timeout(ONBOARDING_TICK_SECONDS):
                onboarded = await run_onboarding_batch(session_factory, config, logger)
    except Exception as error:
        logger.warning(
            "scheduler_run_id=%s onboarding_status=deferred error_category=%s",
            scheduler_run_id,
            error.code if isinstance(error, MonitoringError) else type(error).__name__,
        )
    try:
        async with session_factory.begin() as session:
            if not await session.scalar(select(func.pg_try_advisory_xact_lock(SCHEDULING_LOCK, 1))):
                logger.info(
                    "scheduler_run_id=%s scheduler_status=already_planning", scheduler_run_id
                )
                return
            queue = MonitoringQueue(session)
            cancelled = await queue.cancel_stale(config=config) if config is not None else 0
            await session.flush()
            expired = await queue.expire_leases()
            enrolled = 0
            offline = 0
            jobs = []
            if config is not None:
                offline = await queue.expire_offline_jobs(config.agent_unavailable_grace_seconds)
                enrollment = MonitoringEnrollmentService(session, config.default_schedule)
                if config.mode == "trusted":
                    enrolled = await enrollment.reconcile_trusted(
                        config.batch_size, allow_http=config.trusted_allow_http
                    )
                else:
                    enrolled = await enrollment.reconcile_approvals(config.batch_size)
                await session.flush()
                jobs = await queue.schedule_due(scheduler_run_id, config=config)
        try:
            async with session_factory.begin() as session:
                cleaned = await MonitoringQueue(session).cleanup_uploads()
        except MonitoringError as error:
            logger.warning(
                "scheduler_run_id=%s cleanup_status=deferred error_category=%s",
                scheduler_run_id,
                error.code,
            )
            cleaned = 0
    except Exception as error:
        raise RuntimeError(f"Monitoring scheduling failed ({type(error).__name__})") from None
    logger.info(
        "scheduler_run_id=%s onboarding_processed=%d schedules_created=%d "
        "scheduled=%d cancelled=%d expired_leases=%d offline_jobs=%d cleaned_uploads=%d",
        scheduler_run_id,
        onboarded,
        enrolled,
        len(jobs),
        cancelled,
        expired,
        offline,
        cleaned,
    )
