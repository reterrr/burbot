"""Read the source, field evidence, and tasks at their respective capture boundaries."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import and_, bindparam, func, or_, select, text
from sqlalchemy.orm import load_only

from extraction.schemas.models import ConcreteValue, ExtractionRun, FieldObservation
from extraction.schemas.selector import Selector, SelectorEvaluation, SelectorVersion
from monitoring.attention import MONITORING_TASKS, OPEN_TASKS
from monitoring.models import MonitoringJob, MonitoringJobSelector, SourceCheckRun
from monitoring.presentation import field_presentations, recorded_id, source_record
from monitoring.review import EVIDENCE_STATUS, OPEN_REVIEW_STATUSES, recorded_selector
from monitoring.security import MonitoringError
from sources.schemas.api import SourceSnapshotResponse
from sources.schemas.models import SourceSnapshot

SETTLED = ("completed", "failed")


async def check_record(session, source_id, *, check_id=None, completed=False):
    query = (
        select(MonitoringJob, SourceCheckRun)
        .outerjoin(SourceCheckRun, SourceCheckRun.job_id == MonitoringJob.id)
        .options(
            load_only(
                MonitoringJob.id,
                MonitoringJob.source_id,
                MonitoringJob.created_at,
                MonitoringJob.completed_at,
                MonitoringJob.status,
                MonitoringJob.error_code,
                MonitoringJob.source_snapshot_id,
                MonitoringJob.extraction_run_id,
                raiseload=True,
            )
        )
        .where(
            MonitoringJob.source_id == source_id,
            MonitoringJob.status.in_(("completed",) if completed else SETTLED),
        )
    )
    if check_id is not None:
        query = query.where(MonitoringJob.id == check_id)
    return (
        await session.execute(
            query.order_by(MonitoringJob.created_at.desc(), MonitoringJob.id.desc()).limit(1)
        )
    ).first()


def check_summary(pair):
    if pair is None:
        return None
    job, check = pair
    return {
        "id": job.id,
        "status": job.status,
        "checkedAt": job.completed_at or (check.processed_at if check else None) or job.created_at,
        "changeStatus": check.change_status if check else None,
        "snapshotId": job.source_snapshot_id,
        "extractionRunId": job.extraction_run_id,
        "errorCode": job.error_code,
    }


async def check_history(session, source_id, offset, limit):
    job = MonitoringJob
    check = SourceCheckRun
    rows = (
        await session.execute(
            select(
                job.id,
                job.status,
                job.source_snapshot_id.label("snapshotId"),
                job.extraction_run_id.label("extractionRunId"),
                job.error_code.label("errorCode"),
                check.change_status.label("changeStatus"),
                func.coalesce(job.completed_at, check.processed_at, job.created_at).label(
                    "checkedAt"
                ),
            )
            .outerjoin(check, check.job_id == job.id)
            .where(job.source_id == source_id, job.status.in_(SETTLED))
            .order_by(job.created_at.desc(), job.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).mappings()
    return [dict(row) for row in rows]


async def capture_snapshot(session, job):
    if job is None or job.source_snapshot_id is None:
        return None
    snapshot = await session.get(SourceSnapshot, job.source_snapshot_id)
    if snapshot is not None and snapshot.source_id == job.source_id:
        return SourceSnapshotResponse.model_validate(snapshot)
    return None


async def captured_results(session, job, check):
    if check is None:
        return {}
    rows = [row for row in check.field_results or [] if row.get("status") in EVIDENCE_STATUS]
    # Older rows can recover their selector through an evaluation owned by this run and pin.
    legacy_ids = {
        row["evaluationId"]
        for row in rows
        if not row.get("selectorUuid") and recorded_id(row.get("evaluationId"))
    }
    by_evaluation = {}
    if legacy_ids:
        by_evaluation = dict(
            (
                await session.execute(
                    select(SelectorEvaluation.id, Selector.uuid)
                    .join(
                        SelectorVersion,
                        SelectorVersion.id == SelectorEvaluation.selector_version_id,
                    )
                    .join(Selector, Selector.id == SelectorVersion.selector_id)
                    .join(
                        MonitoringJobSelector,
                        and_(
                            MonitoringJobSelector.version_id == SelectorVersion.id,
                            MonitoringJobSelector.selector_id == Selector.id,
                        ),
                    )
                    .where(
                        Selector.source_id == job.source_id,
                        MonitoringJobSelector.job_id == job.id,
                        SelectorEvaluation.id.in_(legacy_ids),
                        SelectorEvaluation.extraction_run_id == job.extraction_run_id,
                        SelectorEvaluation.source_snapshot_id == job.source_snapshot_id,
                    )
                )
            ).all()
        )
    results = {}
    for row in rows:
        identity = row.get("selectorUuid") or by_evaluation.get(row.get("evaluationId"))
        try:
            identity = UUID(str(identity))
        except ValueError:
            continue
        results[identity] = {**row, "selectorUuid": str(identity)}
    return results


def task_summary(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "workflowStatus": row["workflow_status"],
        "originCheckId": row["job_id"],
        "snapshotId": row["source_snapshot_id"],
        "checkedAt": row["completed_at"],
        "requiresReview": (
            row["status"] in OPEN_REVIEW_STATUSES and row["workflow_status"] == "active"
        ),
    }


async def linked_tasks(session, source_id, results):
    ids = {row["taskId"] for row in results.values() if recorded_id(row.get("taskId"))}
    if not ids:
        return {}
    query = text(f"SELECT * FROM ({MONITORING_TASKS}) t WHERE source_id = :source AND id IN :ids")
    rows = await session.execute(
        query.bindparams(bindparam("ids", expanding=True)),
        {"source": source_id, "ids": sorted(ids)},
    )
    return {row["id"]: task_summary(row) for row in rows.mappings()}


async def older_tasks(session, source_id, latest_id, offset, limit):
    query = f"""
        FROM ({MONITORING_TASKS}) t WHERE {OPEN_TASKS} AND source_id = :source
        AND job_id IS DISTINCT FROM CAST(:latest AS uuid)
    """
    params = {"source": source_id, "latest": latest_id, "offset": offset, "limit": limit}
    total = await session.scalar(text(f"SELECT count(*) {query}"), params)
    rows = (
        await session.execute(
            text(f"""
        SELECT * {query} ORDER BY created_at DESC, id DESC OFFSET :offset LIMIT :limit
    """),
            params,
        )
    ).mappings()
    return {
        "items": [task_summary(row) for row in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


async def evidence_values(session, source_id, identities):
    if not identities:
        return {}
    rows = (
        await session.execute(
            select(
                FieldObservation.id,
                FieldObservation.extraction_run_id,
                ConcreteValue.raw_value,
            )
            .join(ExtractionRun, ExtractionRun.id == FieldObservation.extraction_run_id)
            .join(
                ConcreteValue,
                or_(
                    ConcreteValue.id == FieldObservation.concrete_value_id,
                    and_(
                        FieldObservation.concrete_value_id.is_(None),
                        ConcreteValue.field_observation_id == FieldObservation.id,
                    ),
                ),
            )
            .where(ExtractionRun.source_id == source_id, FieldObservation.id.in_(identities))
            .order_by(FieldObservation.id, ConcreteValue.value_index, ConcreteValue.id)
        )
    ).all()
    observed = defaultdict(list)
    for identity, run_id, value in rows:
        observed[identity, run_id].append(value)
    return {
        identity: (run_id, values[0] if len(values) == 1 else values)
        for (identity, run_id), values in observed.items()
    }


async def field_contexts(session, source_id, selectors, results, job):
    field_slots = {}
    for selector in selectors:
        slot_id = results.get(selector.uuid, {}).get(
            "businessObjectFieldId", selector.business_object_field_id
        )
        field_slots[selector.uuid] = (
            selector.business_entity_field_id,
            slot_id if recorded_id(slot_id) else None,
        )
    presentations = await field_presentations(session, field_slots.values())
    observations = await evidence_values(
        session,
        source_id,
        {
            identity
            for row in results.values()
            for identity in (
                row.get("observationId"),
                row.get("previousObservationId", row.get("baselineObservationId")),
            )
            if recorded_id(identity)
        },
    )
    tasks = await linked_tasks(session, source_id, results)
    contexts = []
    for selector in selectors:
        row = results.get(selector.uuid, {})
        previous = row.get("previousObservationId", row.get("baselineObservationId"))
        current = row.get("observationId")
        current_run, current_value = observations.get(current, (None, None))
        contexts.append(
            {
                **presentations[field_slots[selector.uuid]],
                "selectorUuid": selector.uuid,
                "selectorVersionId": row.get("selectorVersionId"),
                "selectorVersionUuid": row.get("selectorVersionUuid"),
                "configured": selector.active_version_id is not None,
                "status": row.get("status"),
                "previousObservationId": previous,
                "observationId": current,
                "previousEvidence": observations.get(previous, (None, None))[1],
                "currentEvidence": current_value
                if job and current_run == job.extraction_run_id
                else None,
                "evaluationId": row.get("evaluationId"),
                "task": tasks.get(row.get("taskId")),
            }
        )
    return contexts


async def source_review(session, source_id, *, check_id, tasks_offset, tasks_limit):
    source = await source_record(session, source_id)
    latest = await check_record(session, source_id)
    completed = (
        latest
        if latest and latest[0].status == "completed"
        else await check_record(session, source_id, completed=True)
    )
    selected = latest
    if check_id is not None and (latest is None or check_id != latest[0].id):
        selected = await check_record(session, source_id, check_id=check_id)
        if selected is None:
            raise MonitoringError(404, "MONITORING_CHECK_NOT_FOUND")
    job, check = selected if selected else (None, None)
    results = await captured_results(session, job, check)
    scope = [Selector.uuid.in_(results)]
    if job is not None:
        scope.append(
            Selector.id.in_(
                select(MonitoringJobSelector.selector_id).where(
                    MonitoringJobSelector.job_id == job.id
                )
            )
        )
    if selected is latest:
        scope.append(Selector.active_version_id.is_not(None))
    selectors = list(
        await session.scalars(
            select(Selector)
            .where(Selector.source_id == source_id, or_(*scope))
            .order_by(Selector.business_entity_field_id, Selector.id)
        )
    )
    return {
        "id": source_id,
        "source": source,
        "latestCheck": check_summary(latest),
        "latestCompletedCheck": check_summary(completed),
        "selectedCheck": check_summary(selected),
        "snapshot": await capture_snapshot(session, job),
        "fields": await field_contexts(session, source_id, selectors, results, job)
        if selectors
        else [],
        "earlierTasks": await older_tasks(
            session, source_id, latest[0].id if latest else None, tasks_offset, tasks_limit
        ),
    }


async def field_review(session, source_id, check_id, selector_uuid):
    selected = await check_record(session, source_id, check_id=check_id)
    if selected is None:
        raise MonitoringError(404, "MONITORING_CHECK_NOT_FOUND")
    job, check = selected
    row = (await captured_results(session, job, check)).get(selector_uuid)
    if row is None:
        raise MonitoringError(404, "MONITORING_FIELD_NOT_FOUND")
    snapshot = await capture_snapshot(session, job)
    run = None
    if snapshot is not None and job.extraction_run_id is not None:
        run = await session.scalar(
            select(ExtractionRun).where(
                ExtractionRun.id == job.extraction_run_id,
                ExtractionRun.source_id == source_id,
                ExtractionRun.source_snapshot_id == snapshot.id,
            )
        )
    selector, evaluation = (
        await recorded_selector(session, job, run, row) if snapshot else (None, None)
    )
    return {
        "selector": selector,
        "evaluation": evaluation,
        "extractionRunId": run.id if run is not None else None,
    }
