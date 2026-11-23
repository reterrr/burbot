"""Read evidence and the effective business value for an existing monitoring task."""

from uuid import UUID

from sqlalchemy import select

from business_layer.schemas.models import BusinessObjectField
from business_layer.services.data import DataService
from extraction.schemas.models import FieldObservation
from extraction.services.repositories import ExtractionRepository
from monitoring.models import MonitoringJob, SourceCheckRun
from monitoring.security import MonitoringError
from sources.schemas.models import SourceSnapshot
from tasks.schemas.models import (
    Task,
    TaskReason,
    TaskReference,
    TaskReferenceType,
    TaskStatus,
    Workflow,
    WorkflowStatus,
)

OPEN_REVIEW_STATUSES = (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)

EVIDENCE_STATUS = {
    "FIELD_NEW": "INITIAL_EVIDENCE",
    "FIELD_UNCHANGED": "UNCHANGED",
    "FIELD_CHANGED": "CHANGED",
    "FIELD_MISSING": "MISSING",
    "FIELD_AMBIGUOUS": "AMBIGUOUS",
    "FIELD_CONFLICT": "CONFLICT",
    "FIELD_EXTRACTION_FAILED": "EXTRACTION_FAILED",
}

REVIEW_TITLES = {
    "FIELD_NEW": "Review initial evidence",
    "FIELD_CHANGED": "Review changed evidence",
    "FIELD_MISSING": "Review missing evidence",
    "FIELD_AMBIGUOUS": "Review ambiguous evidence",
    "FIELD_CONFLICT": "Review conflicting evidence",
    "FIELD_EXTRACTION_FAILED": "Review evidence extraction failure",
}


def evidence_changed(status):
    return {"FIELD_UNCHANGED": False, "FIELD_CHANGED": True}.get(status)


async def observation_text(repo, observation_id):
    if observation_id is None:
        return None
    observation = await repo.get(FieldObservation, observation_id)
    values = [value.raw_value for value in await repo.observation_values(observation)]
    return values[0] if len(values) == 1 else values


async def source_review_detail(session, job, check, task_id):
    previous_id = await session.scalar(
        select(TaskReference.reference_id)
        .where(
            TaskReference.task_id == task_id,
            TaskReference.reference_type == TaskReferenceType.SOURCE_SNAPSHOT,
            TaskReference.metadata_json["snapshotPosition"].as_string() == "previous",
        )
        .order_by(TaskReference.id)
        .limit(1)
    )
    previous = await session.get(SourceSnapshot, previous_id) if previous_id is not None else None
    current = await session.get(SourceSnapshot, job.source_snapshot_id)
    return {
        "reviewType": "source",
        "changeStatus": check.change_status,
        "previousSnapshotId": previous_id,
        "currentSnapshotId": current.id,
        "previousContentHash": previous.content_hash if previous else None,
        "currentContentHash": current.content_hash,
        "previousStructureHash": previous.structure_hash if previous else None,
        "currentStructureHash": current.structure_hash,
    }


async def review_detail(session, task_id):
    row = (
        await session.execute(
            select(Task, Workflow.status)
            .join(Workflow, Workflow.id == Task.workflow_id)
            .where(Task.id == task_id)
        )
    ).one_or_none()
    if row is None:
        raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND")
    task, workflow_status = row
    metadata = task.metadata_json or {}
    if not metadata.get("monitoringKey") or not metadata.get("monitoringJobId"):
        raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND")
    try:
        job_id = UUID(metadata["monitoringJobId"])
    except (ValueError, TypeError, AttributeError):
        raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND") from None
    job = await session.get(MonitoringJob, job_id)
    check = await session.get(SourceCheckRun, job_id)
    if job is None or check is None:
        raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND")
    context = {
        "taskId": task.id,
        "taskStatus": task.status,
        "sourceId": job.source_id,
        "monitoringJobId": job_id,
        "changeTimestamp": check.acquired_at,
        "requiresReview": (
            workflow_status == WorkflowStatus.ACTIVE and task.status in OPEN_REVIEW_STATUSES
        ),
    }
    if task.reason == TaskReason.SOURCE_CHANGED:
        if job.source_snapshot_id is None:
            raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND")
        return {**context, **await source_review_detail(session, job, check, task_id)}

    field = next((row for row in check.field_results or [] if row.get("taskId") == task_id), None)
    if field is None:
        raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND")

    slot_id = field.get("businessObjectFieldId")
    if "businessObjectFieldId" not in field:
        # Older jobs stored the slot only as a TaskReference.
        slot_id = await session.scalar(
            select(TaskReference.reference_id)
            .where(
                TaskReference.task_id == task_id,
                TaskReference.reference_type == TaskReferenceType.BUSINESS_OBJECT_FIELD,
            )
            .limit(1)
        )
    slot = await session.get(BusinessObjectField, slot_id) if slot_id is not None else None
    canonical = None
    if slot is not None:
        obj = await DataService(session).get_object(slot.business_object_id)
        canonical = next((item for item in obj.fields if item.object_field_id == slot.id), None)

    previous = field.get("previousObservationId", field.get("baselineObservationId"))
    current = field.get("observationId")
    repo = ExtractionRepository(session)
    return {
        **context,
        "reviewType": "field",
        "sourceSnapshotId": job.source_snapshot_id,
        "businessObjectFieldId": slot_id,
        "selectorVersionId": field.get("selectorVersionId"),
        "selectorVersionUuid": field.get("selectorVersionUuid"),
        "canonicalValueId": canonical.value_id if canonical else None,
        "canonicalValue": canonical.value if canonical else None,
        "previousObservationId": previous,
        "observationId": current,
        "previousEvidence": await observation_text(repo, previous),
        "currentEvidence": await observation_text(repo, current),
        "evaluationId": field.get("evaluationId"),
        "baselineObservationId": field.get("baselineObservationId"),
        "comparison": field.get("comparison", "accepted_baseline" if previous else None),
        "evidenceStatus": field.get("evidenceStatus", EVIDENCE_STATUS.get(field["status"])),
        "evidenceChanged": field.get("evidenceChanged", evidence_changed(field["status"])),
    }
