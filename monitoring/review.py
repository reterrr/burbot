"""Read evidence and the effective business value for an existing monitoring task."""

from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select

from business_layer.services.presentation import BusinessPresentation
from extraction.schemas.models import ExtractionRun, FieldObservation
from extraction.schemas.selector import Selector, SelectorEvaluation, SelectorVersion
from extraction.schemas.selector_tree import SelectorDefinition
from extraction.services.repositories import ExtractionRepository
from extraction.services.selector_execution import response as evaluation_response
from extraction.services.selectors import SelectorService
from monitoring.models import MonitoringJob, MonitoringJobSelector, SourceCheckRun
from monitoring.security import MonitoringError
from sources.schemas.api import SourceSnapshotResponse
from sources.schemas.models import SourceSnapshot
from sources.services.sources import SourcesService
from tasks.schemas.models import Task, TaskReference, TaskReferenceType, TaskStatus, Workflow

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


def recorded_id(value):
    return type(value) is int and 0 < value < 2**63


async def recorded_selector(session, job, run, field):
    evaluation = None
    evaluation_id = field.get("evaluationId")
    if run is not None and recorded_id(evaluation_id):
        candidate = await session.get(SelectorEvaluation, evaluation_id)
        if (
            candidate is not None
            and candidate.extraction_run_id == run.id
            and candidate.source_snapshot_id == run.source_snapshot_id
        ):
            evaluation = candidate

    try:
        selector_uuid, version_uuid = (
            UUID(str(value)) if value is not None else None
            for value in (field.get("selectorUuid"), field.get("selectorVersionUuid"))
        )
    except ValueError:
        return None, None, None
    version_id = field.get("selectorVersionId")
    if version_id is not None and not recorded_id(version_id):
        return None, None, None
    if version_id is None and version_uuid is None:
        if evaluation is not None:
            version_id = evaluation.selector_version_id
        elif selector_uuid is None:
            return None, None, None

    # The job pin identifies the executed definition even after another version is approved.
    query = (
        select(Selector, SelectorVersion)
        .select_from(MonitoringJobSelector)
        .join(Selector, Selector.id == MonitoringJobSelector.selector_id)
        .join(SelectorVersion, SelectorVersion.id == MonitoringJobSelector.version_id)
        .where(
            MonitoringJobSelector.job_id == job.id,
            Selector.source_id == job.source_id,
            SelectorVersion.selector_id == Selector.id,
        )
    )
    if selector_uuid is not None:
        query = query.where(Selector.uuid == selector_uuid)
    if version_uuid is not None:
        query = query.where(SelectorVersion.uuid == version_uuid)
    if version_id is not None:
        query = query.where(SelectorVersion.id == version_id)
    pair = (await session.execute(query)).one_or_none()
    if pair is None:
        return None, None, None
    selector, version = pair

    identity_data = {**selector.metadata_json, "uuid": selector.uuid}
    if version.status == "active" and selector.active_version_id == version.id:
        identity_data["activeVersionUuid"] = version.uuid
    try:
        identity = SelectorDefinition.model_validate(identity_data)
        definition = await SelectorService(session).definition(version, selector.uuid)
    except ValidationError:
        return None, None, selector.business_entity_field_id

    diagnostics = None
    if evaluation is not None and evaluation.selector_version_id == version.id:
        try:
            stored = evaluation_response(evaluation)
        except ValidationError:
            # Older or incomplete reports still have inspectable selector definitions.
            pass
        else:
            if stored.result.selector_version_uuid == version.uuid:
                diagnostics = stored.portable()
    return (
        {
            "identity": identity.portable(),
            "versionId": version.id,
            "version": definition.portable(),
        },
        diagnostics,
        selector.business_entity_field_id,
    )


async def review_detail(session, task_id):
    task = await session.get(Task, task_id)
    metadata = (task.metadata_json or {}) if task else {}
    try:
        job_id = UUID(str(metadata.get("monitoringJobId")))
    except ValueError:
        raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND") from None
    check = await session.get(SourceCheckRun, job_id)
    field = (
        next(
            (row for row in (check.field_results or []) if row.get("taskId") == task_id),
            None,
        )
        if check
        else None
    )
    job = await session.get(MonitoringJob, job_id) if field is not None else None
    workflow = await session.get(Workflow, task.workflow_id) if job is not None else None
    if workflow is None or workflow.source_id != job.source_id:
        raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND")

    # An active workflow can move forward while its task keeps the original capture.
    job_references = {
        TaskReferenceType.SOURCE: job.source_id,
        TaskReferenceType.SOURCE_SNAPSHOT: job.source_snapshot_id,
        TaskReferenceType.EXTRACTION_RUN: job.extraction_run_id,
    }
    references = (
        await session.execute(
            select(TaskReference.reference_type, TaskReference.reference_id)
            .where(
                TaskReference.task_id == task_id,
                TaskReference.reference_type.in_(
                    (
                        *job_references,
                        TaskReferenceType.BUSINESS_FIELD,
                        TaskReferenceType.BUSINESS_OBJECT_FIELD,
                    )
                ),
            )
            .order_by(TaskReference.id)
        )
    ).all()
    if any(
        job_references.get(kind) is not None and job_references[kind] != identity
        for kind, identity in references
    ):
        raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND")

    source = await SourcesService(session).get_source(job.source_id)
    snapshot = (
        await session.get(SourceSnapshot, job.source_snapshot_id)
        if job.source_snapshot_id is not None
        else None
    )
    if snapshot is not None and snapshot.source_id != source.id:
        raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND")
    run = (
        await session.get(ExtractionRun, job.extraction_run_id)
        if snapshot is not None and job.extraction_run_id is not None
        else None
    )
    if run is not None and (
        run.source_id != source.id
        or run.source_snapshot_id != snapshot.id
        or run.workflow_id not in (None, workflow.id)
    ):
        run = None
    selector, evaluation, field_id = (
        await recorded_selector(session, job, run, field)
        if snapshot is not None
        else (None, None, None)
    )

    slot_id = field.get("businessObjectFieldId")
    if "businessObjectFieldId" not in field:
        # Older jobs stored the slot only as a TaskReference.
        slot_id = next(
            (
                identity
                for kind, identity in references
                if kind == TaskReferenceType.BUSINESS_OBJECT_FIELD
            ),
            None,
        )
    if field_id is None and slot_id is None:
        field_id = next(
            (identity for kind, identity in references if kind == TaskReferenceType.BUSINESS_FIELD),
            None,
        )
    binding = (slot_id, field_id)
    context = (await BusinessPresentation(session).business_contexts([binding]))[binding]

    previous = field.get("previousObservationId", field.get("baselineObservationId"))
    current = field.get("observationId")
    status = field.get("status")
    repo = ExtractionRepository(session)
    return {
        "taskId": task.id,
        "taskStatus": task.status,
        **context,
        "businessObjectFieldId": slot_id,
        "previousObservationId": previous,
        "observationId": current,
        "previousEvidence": await observation_text(repo, previous),
        "currentEvidence": await observation_text(repo, current),
        "evaluationId": field.get("evaluationId"),
        "selector": selector,
        "evaluation": evaluation,
        "source": {"id": source.id, "url": source.url},
        "snapshot": SourceSnapshotResponse.model_validate(snapshot)
        if snapshot is not None
        else None,
        "extractionRunId": run.id if run is not None else None,
        "extractionRunStatus": run.status if run is not None else None,
        "baselineObservationId": field.get("baselineObservationId"),
        "comparison": field.get("comparison", "accepted_baseline" if previous else None),
        "evidenceStatus": field.get("evidenceStatus", EVIDENCE_STATUS.get(status)),
        "evidenceChanged": field.get("evidenceChanged", evidence_changed(status)),
        "requiresReview": task.status in OPEN_REVIEW_STATUSES,
    }
