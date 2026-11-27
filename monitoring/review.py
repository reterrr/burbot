"""Read evidence and the effective business value for an existing monitoring task."""

from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select

from extraction.schemas.models import ExtractionRun, FieldObservation
from extraction.schemas.selector import Selector, SelectorEvaluation, SelectorVersion
from extraction.schemas.selector_tree import SelectorDefinition
from extraction.services.repositories import ExtractionRepository
from extraction.services.selector_execution import response as evaluation_response
from extraction.services.selectors import SelectorService
from monitoring.archives import archive_summary
from monitoring.models import MonitoringJob, MonitoringJobSelector, SourceCheckRun
from monitoring.presentation import display_text, field_presentations, recorded_id, source_record
from monitoring.security import MonitoringError
from sources.schemas.api import SourceSnapshotResponse
from sources.schemas.models import SourceSnapshot
from tasks.schemas.models import (
    Task,
    TaskReference,
    TaskReferenceType,
    TaskStatus,
    TaskType,
    Workflow,
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
        return None, None
    version_id = field.get("selectorVersionId")
    if version_id is not None and not recorded_id(version_id):
        return None, None
    if version_id is None and version_uuid is None:
        if evaluation is not None:
            version_id = evaluation.selector_version_id
        elif selector_uuid is None:
            return None, None

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
        return None, None
    selector, version = pair

    identity_data = {**selector.metadata_json, "uuid": selector.uuid}
    if version.status == "active" and selector.active_version_id == version.id:
        identity_data["activeVersionUuid"] = version.uuid
    try:
        identity = SelectorDefinition.model_validate(identity_data)
        definition = await SelectorService(session).definition(version, selector.uuid)
    except ValidationError:
        return None, None

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
    return {
        "identity": identity.portable(),
        "versionId": version.id,
        "version": definition.portable(),
    }, diagnostics


def reference_displays(references, source, snapshot, run, context, observations):
    labels = {(TaskReferenceType.SOURCE, source["id"]): {"label": source["name"] or source["url"]}}
    if snapshot is not None:
        labels[TaskReferenceType.SOURCE_SNAPSHOT, snapshot.id] = {"capturedAt": snapshot.fetched_at}
    if run is not None:
        labels[TaskReferenceType.EXTRACTION_RUN, run.id] = {"status": run.status}
    for observation_id, evidence in observations.items():
        texts = evidence if isinstance(evidence, list) else [evidence]
        if text := " · ".join(filter(None, map(display_text, texts))):
            labels[TaskReferenceType.OBSERVATION, observation_id] = {"label": text}
    field, obj = context["businessField"], context["businessObject"]
    if field is not None and field["name"]:
        labels[TaskReferenceType.BUSINESS_FIELD, field["id"]] = {"label": field["name"]}
        if obj is not None:
            slot_label = " · ".join(filter(None, (field["name"], obj["name"])))
            labels[TaskReferenceType.BUSINESS_OBJECT_FIELD, context["businessObjectFieldId"]] = {
                "label": slot_label,
            }
    if obj is not None and obj["name"]:
        labels[TaskReferenceType.BUSINESS_OBJECT, obj["id"]] = {"label": obj["name"]}
    return {
        ref.id: display
        for ref in references
        if (display := labels.get((ref.reference_type, ref.reference_id)))
    }


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
        await session.scalars(
            select(TaskReference).where(TaskReference.task_id == task_id).order_by(TaskReference.id)
        )
    ).all()
    object_review = task.type == TaskType.REVIEW_BUSINESS_OBJECT
    for kind, identity in job_references.items():
        if identity is None:
            continue
        attached = {ref.reference_id for ref in references if ref.reference_type == kind}
        # The legacy endpoint keeps reading the originating capture. Object reviews can
        # also reference later, distinct findings from the same source.
        if (object_review and identity not in attached) or (
            not object_review and attached - {identity}
        ):
            raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND")

    source = await source_record(session, job.source_id)
    snapshot = (
        await session.get(SourceSnapshot, job.source_snapshot_id)
        if job.source_snapshot_id is not None
        else None
    )
    if snapshot is not None and snapshot.source_id != source["id"]:
        raise MonitoringError(404, "MONITORING_REVIEW_NOT_FOUND")
    run = (
        await session.get(ExtractionRun, job.extraction_run_id)
        if snapshot is not None and job.extraction_run_id is not None
        else None
    )
    if run is not None and (
        run.source_id != source["id"]
        or run.source_snapshot_id != snapshot.id
        or run.workflow_id not in (None, workflow.id)
    ):
        run = None
    selector, evaluation = (
        await recorded_selector(session, job, run, field) if snapshot is not None else (None, None)
    )

    slot_id = field.get("businessObjectFieldId")
    if "businessObjectFieldId" not in field:
        # Older jobs stored the slot only as a TaskReference.
        slot_id = next(
            (
                ref.reference_id
                for ref in references
                if ref.reference_type == TaskReferenceType.BUSINESS_OBJECT_FIELD
            ),
            None,
        )
    field_id = field.get("businessFieldId") or next(
        (
            ref.reference_id
            for ref in references
            if ref.reference_type == TaskReferenceType.BUSINESS_FIELD
        ),
        None,
    )
    pair = (field_id, slot_id if recorded_id(slot_id) else None)
    context = (await field_presentations(session, [pair]))[pair]

    previous = field.get("previousObservationId", field.get("baselineObservationId"))
    current = field.get("observationId")
    status = field.get("status")
    repo = ExtractionRepository(session)
    previous_evidence = await observation_text(repo, previous)
    current_evidence = await observation_text(repo, current)
    review_source = {"id": source["id"], "url": source["url"]}
    if source["name"] is not None:
        review_source["name"] = source["name"]
    return {
        **context,
        "taskId": task.id,
        "checkId": job.id,
        "archive": archive_summary(job),
        "taskStatus": task.status,
        "businessObjectFieldId": slot_id,
        "previousObservationId": previous,
        "observationId": current,
        "previousEvidence": previous_evidence,
        "currentEvidence": current_evidence,
        "evaluationId": field.get("evaluationId"),
        "selector": selector,
        "evaluation": evaluation,
        "source": review_source,
        "snapshot": SourceSnapshotResponse.model_validate(snapshot)
        if snapshot is not None
        else None,
        "extractionRunId": run.id if run is not None else None,
        "baselineObservationId": field.get("baselineObservationId"),
        "comparison": field.get("comparison", "accepted_baseline" if previous else None),
        "evidenceStatus": field.get("evidenceStatus", EVIDENCE_STATUS.get(status)),
        "evidenceChanged": field.get("evidenceChanged", evidence_changed(status)),
        "requiresReview": task.status in OPEN_REVIEW_STATUSES,
        "referenceDisplays": reference_displays(
            references,
            source,
            snapshot,
            run,
            context,
            {previous: previous_evidence, current: current_evidence},
        ),
    }
