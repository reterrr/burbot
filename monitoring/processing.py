"""Turn a verified upload into Sources, Extraction, and Tasks records."""

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from business_layer.schemas.models import BusinessObjectField
from extraction.schemas import capture as capture_dto
from extraction.schemas.common import utc_now
from extraction.schemas.enums import ExtractionRunStatus, ObservationStatus
from extraction.schemas.evidence import TokenClass
from extraction.schemas.models import ExtractionRun, FieldObservation
from extraction.schemas.selector import SelectorEvaluation, SelectorVersion
from extraction.services.capture import CaptureService
from extraction.services.tracking import BASELINE_STATUSES, comparable_value
from monitoring.models import (
    PROCESSABLE,
    MonitoringJob,
    MonitoringSource,
    MonitoringUpload,
    SourceCheckRun,
)
from monitoring.queue import PROCESSING_LIMIT, MonitoringQueue, retry_delay
from monitoring.review import (
    EVIDENCE_STATUS,
    OPEN_REVIEW_STATUSES,
    REVIEW_TITLES,
    evidence_changed,
)
from monitoring.security import MonitoringError, fingerprint
from sources.schemas import api as source_dto
from sources.schemas.models import SourceCheckSchedule, SourceFieldTracking, SourceSnapshot
from sources.services.sources import SourcesService
from tasks.api.dto import TaskCreateRequest, TaskReferenceCreate, WorkflowStartRequest
from tasks.exceptions.exceptions import TaskError
from tasks.schemas.models import (
    Task,
    TaskReason,
    TaskStatus,
    TaskType,
)
from tasks.services.task import TasksService

HASH_FIELDS = (
    "representation",
    "representation_version",
    "structure_hash_version",
    "hash_algorithm",
)
FAILURES = {
    "not_found": ("FIELD_MISSING", "VALUE_NOT_FOUND", TaskReason.VALUE_MISSING),
    "ambiguous": ("FIELD_AMBIGUOUS", "AMBIGUOUS_MATCH", TaskReason.VALUE_CONFLICT),
    "conflict": ("FIELD_CONFLICT", "AMBIGUOUS_MATCH", TaskReason.VALUE_CONFLICT),
    "error": ("FIELD_EXTRACTION_FAILED", "SELECTOR_BROKEN", TaskReason.EXTRACTION_FAILED),
    "unsupported": ("FIELD_EXTRACTION_FAILED", "SELECTOR_BROKEN", TaskReason.EXTRACTION_FAILED),
}


def acquisition_change(previous, hashes, completion):
    if (
        previous is None
        or previous.file_id is None
        or any(getattr(previous, name) != value for name, value in hashes.items())
    ):
        return "INITIAL_FETCH"
    content = previous.content_hash != completion["contentHash"]
    structure = previous.structure_hash != completion["structureHash"]
    return {
        (False, False): "UNCHANGED",
        (True, False): "CONTENT_CHANGED",
        (False, True): "STRUCTURE_CHANGED",
        (True, True): "CONTENT_AND_STRUCTURE_CHANGED",
    }[content, structure]


class MonitoringProcessor:
    """Call acquisition, processing and failure registration in separate transactions."""

    def __init__(self, session):
        self.session = session
        self.queue = MonitoringQueue(session)
        self.sources = SourcesService(session, commit=False)
        self.capture = CaptureService(session, commit=False)
        self.tasks = TasksService(session, commit=False)

    async def _lock(self, job_id, *, lock_workflow=False):
        job = await self.session.get(MonitoringJob, job_id)
        if job is None or job.status not in PROCESSABLE:
            return None, None
        if lock_workflow:
            # Keep the same workflow/source lock order as manual captures.
            await self.tasks._get_current_workflow(job.source_id, for_update=True)
        source = await self.queue._source(job.source_id)
        await self.session.refresh(job, with_for_update=True)
        if job.status not in PROCESSABLE or job.available_at > utc_now():
            return None, None
        check = await self.session.get(SourceCheckRun, job_id)
        try:
            self.queue._check_policy(
                source, await self.session.get(MonitoringSource, source.id), job
            )
        except MonitoringError as error:
            self.queue._finish(job, "cancelled", error.code)
            return None, None
        return job, check

    async def acquire(self, job_id, flow_id=None):
        job, check = await self._lock(job_id)
        if job is None:
            return False
        check.processing_flow_run_id = flow_id
        if check.acquired_at is not None:
            return True

        data = job.completion_json
        intent = await self.session.get(MonitoringUpload, UUID(data["uploadIntentId"]))
        if intent is None or not intent.sealed_key or intent.cleaned_at is not None:
            raise MonitoringError(409, "SEALED_UPLOAD_MISSING")
        latest = await self.session.scalar(
            select(SourceSnapshot)
            .where(SourceSnapshot.source_id == job.source_id)
            .order_by(SourceSnapshot.fetched_at.desc(), SourceSnapshot.id.desc())
            .limit(1)
        )
        hashes = dict(
            zip(
                HASH_FIELDS,
                (
                    data["representation"],
                    data["representationVersion"],
                    data["structureHashVersion"],
                    data["hashAlgorithm"],
                ),
                strict=True,
            )
        )
        now = utc_now()
        check.change_status = acquisition_change(latest, hashes, data)
        snapshot_id = latest.id if latest is not None else None
        if check.change_status != "UNCHANGED":
            stored_file = await self.sources.register_file(
                source_dto.StoredFileCreateRequest(
                    storage_key=intent.sealed_key,
                    mime_type=data["mimeType"],
                    size_bytes=intent.content_size,
                    sha256=intent.content_hash,
                )
            )
            snapshot = await self.sources.create_snapshot(
                job.source_id,
                source_dto.SourceSnapshotCreate(
                    file_id=stored_file.id,
                    page_url=data["pageUrl"],
                    fetched_at=now,
                    mime_type=data["mimeType"],
                    content_hash=data["contentHash"],
                    structure_hash=data["structureHash"],
                    **hashes,
                ),
            )
            snapshot_id = snapshot.id

        await self.sources.set_metadata(
            job.source_id,
            source_dto.SourceMetadataWrite(
                latest_content_hash=data["contentHash"],
                latest_structure_hash=data["structureHash"],
                hashes_updated_at=now,
            ),
        )
        schedule = await self.session.get(SourceCheckSchedule, job.source_id)
        if schedule is not None:
            await self.sources.set_schedule(
                job.source_id,
                source_dto.SourceCheckScheduleWrite(
                    interval_seconds=schedule.interval_seconds,
                    enabled=schedule.enabled,
                    last_checked_at=now,
                    next_check_at=now + timedelta(seconds=schedule.interval_seconds),
                ),
            )
        job.source_snapshot_id = snapshot_id
        if data["evaluations"]:
            run = await self.capture.create_run(
                capture_dto.CreateRunRequest(
                    snapshot_id=snapshot_id,
                    extractor_version=data["representationVersion"],
                )
            )
            job.extraction_run_id = run.id
        job.status = "processing"
        check.acquired_at = now
        return True

    async def _payload(self, job, pins):
        data = job.completion_json
        reports = {r["result"]["selectorVersionUuid"]: r["result"] for r in data["evaluations"]}
        root = await self.capture.repo.current_scope(job.source_id, "ROOT")
        document_selector = {"type": "CSS", "value": "html", "discovered_by": "AUTOMATIC"}
        scope = {"client_key": "document", "name": "ROOT", "selector": document_selector}
        if root is not None:
            scope.update(
                business_entity_id=root.business_entity_id,
                selector={
                    "type": root.selector_type,
                    "value": root.selector_string,
                    "confidence": root.confidence_score,
                    "discovered_by": root.discovered_by,
                },
            )
        scopes = [scope]
        instances = [
            {
                "client_key": "document",
                "scope_client_key": "document",
                "root_element_client_key": "document",
            }
        ]
        values, issues, evaluations = [], [], {}
        await self.capture.repo.get_or_create(TokenClass, {"id": "text"}, {"name": "Text"})
        for _, version, selector in pins:
            key = f"selector-{selector.uuid}"
            report = reports[str(version.uuid)]
            field = await self.capture.repo.field(selector.business_entity_field_id)
            slot = None
            if selector.business_object_field_id is not None:
                slot = await self.session.get(
                    BusinessObjectField, selector.business_object_field_id
                )
                if slot is None or slot.business_entity_field_id != field.id:
                    raise MonitoringError(409, "SELECTOR_BINDING_CHANGED")
            scopes.append(
                {
                    "client_key": key,
                    "parent_client_key": "document",
                    "name": key,
                    "business_entity_id": field.business_entity_id,
                    "selector": document_selector,
                }
            )
            instances.append(
                {
                    "client_key": key,
                    "scope_client_key": key,
                    "parent_client_key": "document",
                    "root_element_client_key": "document",
                }
            )
            evaluations[key] = SelectorEvaluation(
                uuid=uuid4(),
                selector_version_id=version.id,
                source_snapshot_id=job.source_snapshot_id,
                extraction_run_id=job.extraction_run_id,
                execution_key=f"{job.id}:{selector.uuid}",
                page_url=data["pageUrl"],
                provenance="browser_agent_reported",
                result_json=report,
            )
            if report["status"] == "success":
                values.append(
                    {
                        "client_key": key,
                        "scope_instance_client_key": key,
                        "element_client_key": "document",
                        "business_entity_field_id": field.id,
                        "business_object_id": slot.business_object_id if slot else None,
                        "token_class_id": "text",
                        "raw_value": report["rawValue"],
                        "discovered_by": "AUTOMATIC",
                    }
                )
            else:
                issues.append(
                    {
                        "code": FAILURES[report["status"]][1],
                        "message": report["status"],
                        "scope_instance_client_key": key,
                        "business_entity_field_id": field.id,
                    }
                )
        return capture_dto.CaptureRequest.model_validate(
            {
                "capture_key": f"monitoring:{job.id}",
                "scopes": scopes,
                "scope_instances": instances,
                "values": values,
                "issues": issues,
                "elements": [
                    {
                        "client_key": "document",
                        "element_from": "HTML",
                        "html": {"tag_name": "html"},
                        "structural_hash": data["structureHash"],
                    }
                ],
            },
            context={"selector_evidence": True},
        ), evaluations

    async def review_task(
        self,
        job,
        outcome,
        reason,
        *,
        selector=None,
        observation=None,
        previous=None,
        values=(),
        legacy_values=None,
        previous_task_id=None,
    ):
        slot_id = selector.business_object_field_id if selector is not None else None
        target = [job.source_id, slot_id or str(selector.uuid if selector else ""), outcome]
        key = fingerprint([*target, values])
        keys = [key]
        if legacy_values is not None:
            keys.append(fingerprint([*target, legacy_values]))
        if previous_task_id is not None:
            previous_task = await self.session.get(Task, previous_task_id)
            if (
                previous_task is not None
                and previous_task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
                and (previous_task.metadata_json or {}).get("monitoringKey") in keys
            ):
                return previous_task

        workflow = await self.tasks._get_current_workflow(job.source_id, for_update=True)
        if workflow is None or workflow.source_snapshot_id != job.source_snapshot_id:
            workflow = (
                await self.tasks.start_source_workflow(
                    job.source_id,
                    WorkflowStartRequest(source_snapshot_id=job.source_snapshot_id),
                )
            ).workflow

        existing = await self.session.scalar(
            select(Task)
            .where(
                Task.workflow_id == workflow.id,
                Task.status.in_(OPEN_REVIEW_STATUSES),
                Task.metadata_json["monitoringKey"].as_string().in_(keys),
            )
            .order_by(Task.id)
            .limit(1)
        )
        if existing is not None:
            return existing

        reference_ids = {
            "source": job.source_id,
            "source_snapshot": job.source_snapshot_id,
            "extraction_run": job.extraction_run_id,
            "observation": observation.id if observation else None,
            "business_field": selector.business_entity_field_id if selector else None,
            "business_object_field": slot_id,
        }
        references = [
            TaskReferenceCreate(role="context", reference_type=kind, reference_id=row_id)
            for kind, row_id in reference_ids.items()
            if row_id is not None
        ]
        if previous is not None:
            references.append(
                TaskReferenceCreate(
                    role="context",
                    reference_type="observation",
                    reference_id=previous.id,
                    metadata_json={"evidencePosition": "previous"},
                )
            )
        return await self.tasks.create_task(
            TaskCreateRequest(
                source_id=job.source_id,
                source_snapshot_id=job.source_snapshot_id,
                type=(
                    TaskType.RESOLVE_OBSERVATION
                    if reason == TaskReason.POSSIBLE_NEW_OBJECT
                    else TaskType.REVIEW_SOURCE_CHANGE
                ),
                reason=reason,
                title=(
                    "Resolve unbound evidence"
                    if reason == TaskReason.POSSIBLE_NEW_OBJECT
                    else REVIEW_TITLES[outcome]
                ),
                metadata_json={
                    "monitoringKey": key,
                    "monitoringJobId": str(job.id),
                    "evidenceStatus": EVIDENCE_STATUS[outcome],
                },
                references=references,
            )
        )

    async def _comparison_evidence(self, job, selector, observed_at):
        slot_id = selector.business_object_field_id
        if slot_id is None:
            return None, None, None, None
        repo = self.capture.repo
        source_field = await self.session.scalar(
            select(SourceFieldTracking.id).where(
                SourceFieldTracking.source_id == job.source_id,
                SourceFieldTracking.business_entity_field_id == selector.business_entity_field_id,
            )
        )
        if source_field is None:
            return None, None, None, None
        tracking = await repo.current_tracking(source_field, slot_id)
        baseline_id = None
        if tracking is not None and tracking.baseline_observation_id is not None:
            baseline = await repo.get(FieldObservation, tracking.baseline_observation_id)
            if (
                baseline.status in BASELINE_STATUSES
                and baseline.business_object_field_id == slot_id
                and baseline.source_field_tracking_id == source_field
                and baseline.observed_at <= observed_at
            ):
                baseline_id = baseline.id
                value = await repo.observation_value(baseline)
                if value is not None:
                    return baseline_id, baseline, value, "accepted_baseline"

        # The tracking's last pointer already includes this capture. Compare the
        # previous observation of this selector across its versions and snapshots.
        previous = await self.session.scalar(
            select(FieldObservation)
            .join(SelectorVersion, SelectorVersion.id == FieldObservation.selector_version_id)
            .where(
                SelectorVersion.selector_id == selector.id,
                FieldObservation.source_field_tracking_id == source_field,
                FieldObservation.business_object_field_id == slot_id,
                FieldObservation.extraction_run_id != job.extraction_run_id,
                FieldObservation.observed_at <= observed_at,
                FieldObservation.concrete_value_id.is_not(None),
                FieldObservation.status.not_in(
                    [ObservationStatus.REJECTED, ObservationStatus.SUPERSEDED]
                ),
            )
            .order_by(FieldObservation.observed_at.desc(), FieldObservation.id.desc())
            .limit(1)
        )
        if previous is None:
            return baseline_id, None, None, None
        return baseline_id, previous, await repo.observation_value(previous), "previous_observation"

    async def _outcome(
        self, job, selector, evaluation, observation_id, observed_at, previous_task_id
    ):
        baseline_id, previous, prior_value, comparison = await self._comparison_evidence(
            job, selector, observed_at
        )
        observed = None
        reason, values, legacy_values = None, (), None
        if observation_id is None:
            outcome, _, reason = FAILURES[evaluation.result_json["status"]]
        else:
            observed = await self.capture.repo.get(FieldObservation, observation_id)
            current = await self.capture.repo.observation_value(observed)
            values = (prior_value.raw_value if prior_value else None, current.raw_value)
            if prior_value is None:
                outcome = "FIELD_NEW"
                reason = (
                    TaskReason.MANUAL
                    if observed.business_object_field_id is not None
                    else TaskReason.POSSIBLE_NEW_OBJECT
                )
            elif values[0] == values[1]:
                outcome = "FIELD_UNCHANGED"
            else:
                outcome, reason = "FIELD_CHANGED", TaskReason.VALUE_CHANGED
            if comparison in (None, "accepted_baseline"):
                # Pending reviews created by older versions retain their deduplication key.
                legacy_values = (
                    comparable_value(prior_value) if prior_value else None,
                    comparable_value(current),
                )

        task = (
            await self.review_task(
                job,
                outcome,
                reason,
                selector=selector,
                observation=observed,
                previous=previous,
                values=values,
                legacy_values=legacy_values,
                previous_task_id=previous_task_id,
            )
            if reason is not None
            else None
        )
        return {
            "selectorUuid": str(selector.uuid),
            "selectorVersionId": evaluation.selector_version_id,
            "selectorVersionUuid": evaluation.result_json["selectorVersionUuid"],
            "evaluationId": evaluation.id,
            "status": outcome,
            "evidenceStatus": EVIDENCE_STATUS[outcome],
            "evidenceChanged": evidence_changed(outcome),
            "requiresReview": task is not None and task.status in OPEN_REVIEW_STATUSES,
            "businessObjectFieldId": selector.business_object_field_id,
            "observationId": observation_id,
            "previousObservationId": previous.id if previous else None,
            "baselineObservationId": baseline_id,
            "comparison": comparison,
            "taskId": task.id if task else None,
        }

    async def _previous_tasks(self, source_id):
        fields = await self.session.scalar(
            select(SourceCheckRun.field_results)
            .join(MonitoringJob, MonitoringJob.id == SourceCheckRun.job_id)
            .where(MonitoringJob.source_id == source_id, MonitoringJob.status == "completed")
            .order_by(SourceCheckRun.processed_at.desc(), MonitoringJob.id.desc())
            .limit(1)
        )
        return {
            row["selectorUuid"]: row["taskId"]
            for row in fields or []
            if row.get("selectorUuid") and row.get("taskId") is not None
        }

    async def process(self, job_id):
        job, check = await self._lock(job_id, lock_workflow=True)
        if job is None or check.acquired_at is None:
            return False
        pins = await self.queue._pins(job)
        results = []
        if pins:
            previous_tasks = await self._previous_tasks(job.source_id)
            request, evaluations = await self._payload(job, pins)
            capture = await self.capture.register_capture(
                job.extraction_run_id,
                request,
                selector_evaluations=evaluations,
                observed_at=check.acquired_at,
            )
            for _, _, selector in pins:
                key = f"selector-{selector.uuid}"
                results.append(
                    await self._outcome(
                        job,
                        selector,
                        evaluations[key],
                        capture.observation_ids_by_client_key.get(key),
                        check.acquired_at,
                        previous_tasks.get(str(selector.uuid)),
                    )
                )
        check.field_results = results
        check.processed_at = utc_now()
        self.queue._finish(job, "completed")
        return True

    async def retry_processing(self, job_id, flow_id=None):
        job, check = await self._lock(job_id, lock_workflow=True)
        if job is None:
            return
        check.processing_flow_run_id = flow_id
        job.processing_attempts += 1
        job.error_code = "PROCESSING_FAILED"
        if job.processing_attempts < PROCESSING_LIMIT:
            job.available_at = utc_now() + retry_delay(job.processing_attempts)
            return
        self.queue._finish(job, "failed", job.error_code)
        check.processed_at = utc_now()
        if check.acquired_at is None:
            schedule = await self.session.get(SourceCheckSchedule, job.source_id)
            if schedule is not None:
                schedule.next_check_at = utc_now() + timedelta(seconds=schedule.interval_seconds)
        if job.extraction_run_id is not None:
            run = await self.session.get(ExtractionRun, job.extraction_run_id, with_for_update=True)
            run.status = ExtractionRunStatus.FAILED
            run.finished_at = utc_now()
            run.error_message = "Monitoring processing retry limit reached"
            outcome = {"status": "FIELD_EXTRACTION_FAILED"}
            try:
                async with self.session.begin_nested():
                    task = await self.review_task(
                        job,
                        "FIELD_EXTRACTION_FAILED",
                        TaskReason.EXTRACTION_FAILED,
                    )
                    outcome["taskId"] = task.id
            except (TaskError, SQLAlchemyError):
                outcome["taskErrorCode"] = "REVIEW_TASK_FAILED"
            check.field_results = [outcome]
