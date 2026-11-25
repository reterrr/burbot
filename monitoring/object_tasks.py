"""Group bound findings into the existing source workflow's BusinessObject tasks."""

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from monitoring.review import EVIDENCE_STATUS, OPEN_REVIEW_STATUSES
from monitoring.security import fingerprint
from tasks.api.dto import TaskCreateRequest, TaskReferenceCreate
from tasks.schemas.models import Task, TaskReason, TaskReference, TaskStatus, TaskType

ISSUE_PRIORITY = {
    "FIELD_NEW": 1,
    "FIELD_CHANGED": 2,
    "FIELD_MISSING": 3,
    "FIELD_AMBIGUOUS": 4,
    "FIELD_CONFLICT": 5,
    "FIELD_EXTRACTION_FAILED": 6,
}


@dataclass
class Finding:
    result: dict
    reason: TaskReason | None
    values: tuple = ()
    legacy_values: tuple | None = None


PREVIOUS_FINDINGS = text("""
    SELECT previous.field
    FROM unnest(CAST(:selectors AS text[])) AS selectors(uuid)
    CROSS JOIN LATERAL (
        SELECT field FROM monitoring_jobs j JOIN source_check_runs c ON c.job_id = j.id
        CROSS JOIN LATERAL jsonb_array_elements(CASE
            WHEN jsonb_typeof(c.field_results) = 'array' THEN c.field_results
            ELSE '[]'::jsonb END) AS fields(field)
        WHERE j.source_id = :source AND j.status = 'completed'
          AND field->>'selectorUuid' = selectors.uuid
        ORDER BY j.created_at DESC, j.id DESC LIMIT 1
    ) previous
""")


async def previous_findings(session, source_id, selectors):
    return {
        row["selectorUuid"]: row
        for row in await session.scalars(
            PREVIOUS_FINDINGS, {"source": source_id, "selectors": selectors}
        )
    }


def review_key(source_id, object_id):
    return fingerprint(["business_object", source_id, object_id])


def same_previous(job, finding, previous, task):
    row = finding.result
    if task is None:
        return False
    if task.type == TaskType.REVIEW_BUSINESS_OBJECT:
        return previous.get("findingKey") == row["findingKey"] and task.status in (
            TaskStatus.COMPLETED,
            TaskStatus.CANCELLED,
        )
    if task.type != TaskType.REVIEW_SOURCE_CHANGE or task.status not in (
        *OPEN_REVIEW_STATUSES,
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
    ):
        return False
    # A matching old field task keeps its existing identity. A new finding can start a group.
    target = [job.source_id, row["businessObjectFieldId"], row["status"]]
    return (task.metadata_json or {}).get("monitoringKey") in {
        fingerprint([*target, values])
        for values in (finding.values, finding.legacy_values)
        if values is not None
    }


def context_references(job, findings):
    refs = {
        ("source", job.source_id),
        ("source_snapshot", job.source_snapshot_id),
        ("extraction_run", job.extraction_run_id),
    }
    for finding in findings:
        row = finding.result
        refs.update(
            (
                ("business_field", row["businessFieldId"]),
                ("business_object_field", row["businessObjectFieldId"]),
                ("observation", row["observationId"]),
                ("observation", row["previousObservationId"]),
            )
        )
    return [
        TaskReferenceCreate(role="context", reference_type=kind, reference_id=identity)
        for kind, identity in sorted(
            (kind, identity) for kind, identity in refs if identity is not None
        )
    ]


async def update_group(session, tasks, job, object_id, rows, task):
    metadata = (
        dict(task.metadata_json)
        if task
        else {
            "monitoringKey": review_key(job.source_id, object_id),
            "monitoringJobId": str(job.id),
        }
    )
    index = dict(metadata.get("monitoringFindings", {}))
    additions = []
    for finding in rows:
        row = finding.result
        uuid = row["selectorUuid"]
        if index.get(uuid, {}).get("findingKey") == row["findingKey"]:
            continue
        # Only an index of current review pointers lives on the task. Evidence and the
        # selector version remain on the immutable check/capture that recorded them.
        additions.append(finding)
        index[uuid] = {
            "checkId": str(job.id),
            "findingKey": row["findingKey"],
            "status": row["status"],
        }
    if additions:
        metadata["monitoringFindings"] = index
        strongest = max(index.values(), key=lambda item: ISSUE_PRIORITY[item["status"]])
        metadata["evidenceStatus"] = EVIDENCE_STATUS[strongest["status"]]
        references = context_references(job, additions)
        if task is None:
            first = max(additions, key=lambda finding: ISSUE_PRIORITY[finding.result["status"]])
            task = await tasks.create_task(
                TaskCreateRequest(
                    source_id=job.source_id,
                    source_snapshot_id=job.source_snapshot_id,
                    type=TaskType.REVIEW_BUSINESS_OBJECT,
                    title="Review business object",
                    reason=first.reason,
                    metadata_json=metadata,
                    references=[
                        TaskReferenceCreate(
                            role="target", reference_type="business_object", reference_id=object_id
                        ),
                        *references,
                    ],
                )
            )
        else:
            task.metadata_json = metadata
            await session.execute(
                insert(TaskReference)
                .values([{"task_id": task.id, **ref.model_dump()} for ref in references])
                .on_conflict_do_nothing(constraint="uq_task_reference")
            )
    return task


async def assign_object_reviews(session, tasks, job, workflow, findings, previous):
    task_ids = {row["taskId"] for row in previous.values() if row.get("taskId") is not None}
    prior_tasks = (
        {task.id: task for task in await session.scalars(select(Task).where(Task.id.in_(task_ids)))}
        if task_ids
        else {}
    )
    groups = defaultdict(list)
    for finding in findings:
        row = finding.result
        prior = previous.get(row["selectorUuid"], {})
        task = prior_tasks.get(prior.get("taskId"))
        if same_previous(job, finding, prior, task):
            row.update(taskId=task.id, requiresReview=task.status in OPEN_REVIEW_STATUSES)
        else:
            groups[row["businessObjectId"]].append(finding)
    if not groups:
        return

    keys = {review_key(job.source_id, identity): identity for identity in groups}
    existing = {}
    if workflow is not None:
        for task in await session.scalars(
            select(Task)
            .where(
                Task.workflow_id == workflow.id,
                Task.type == TaskType.REVIEW_BUSINESS_OBJECT,
                Task.status.in_(OPEN_REVIEW_STATUSES),
                Task.metadata_json["monitoringKey"].as_string().in_(keys),
            )
            .order_by(Task.id)
            .execution_options(populate_existing=True)
        ):
            existing.setdefault(keys[task.metadata_json["monitoringKey"]], task)
    for identity, rows in groups.items():
        task = await update_group(session, tasks, job, identity, rows, existing.get(identity))
        for finding in rows:
            finding.result.update(taskId=task.id, requiresReview=True)
