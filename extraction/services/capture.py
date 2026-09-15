"""Transaction and lifecycle coordination for snapshot-based extraction."""

import hashlib
import json
from copy import deepcopy

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from extraction.exceptions import (
    ExtractionConflict,
    ExtractionError,
    ExtractionNotConfigured,
    ExtractionValidationError,
)
from extraction.schemas import capture as dto
from extraction.schemas.enums import DiscoveryMethod, ExtractionRunStatus, ObservationStatus
from extraction.schemas.evidence import Element, ExtractionCapture, ScopeInstance, TokenClass
from extraction.schemas.models import ExtractionRun, FieldObservation, utc_now
from extraction.services.adapters import ExtractionDefinitions, SnapshotExtractor
from extraction.services.capture_writer import CaptureWriter
from extraction.services.repositories import ExtractionRepository
from extraction.services.tracking import update_tracking_from_observation
from sources.exceptions import SourceConflict
from sources.schemas.enums import SourceState
from sources.schemas.models import SourceFieldTracking
from tasks.schemas.models import Workflow, WorkflowStatus


def payload_hash(request: dto.CaptureRequest) -> str:
    return hashlib.sha256(
        json.dumps(
            request.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def definitions_fingerprint(definitions):
    """Include semantic content, not just row IDs (including legacy/corrupt rows)."""
    return hashlib.sha256(
        json.dumps(
            [
                [r.model_dump(mode="json") for r in sorted(rows, key=lambda r: r.id)]
                for rows in definitions
            ],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


class CaptureService:
    def __init__(self, session: AsyncSession, extractor: SnapshotExtractor | None = None):
        self.session = session
        self.repo = ExtractionRepository(session)
        self.extractor = extractor

    @staticmethod
    def run_response(run: ExtractionRun) -> dto.RunResponse:
        return dto.RunResponse(**run.model_dump(), snapshot_id=run.source_snapshot_id)

    async def _source(self, source_id):
        source = await self.repo.lock_source(source_id)
        if source.state == SourceState.ARCHIVED:
            raise ExtractionConflict("Source is archived")
        return source

    async def create_run(self, request: dto.CreateRunRequest) -> dto.RunResponse:
        try:
            snapshot = await self.repo.get_snapshot(request.snapshot_id)
            # Workflow -> Source -> Run is the common lock order for workflow captures.
            if request.workflow_id is not None:
                workflow = await self.repo.get(Workflow, request.workflow_id, lock=True)
                if (
                    workflow.source_id != snapshot.source_id
                    or workflow.source_snapshot_id != snapshot.id
                ):
                    raise ExtractionValidationError(
                        "Workflow and snapshot must describe the same source snapshot"
                    )
                if workflow.status != WorkflowStatus.ACTIVE:
                    raise ExtractionConflict("Workflow is not active")
            await self._source(snapshot.source_id)
            run = await self.repo.add(
                ExtractionRun(
                    source_id=snapshot.source_id,
                    source_snapshot_id=snapshot.id,
                    workflow_id=request.workflow_id,
                    extractor_version=request.extractor_version,
                    status=ExtractionRunStatus.PENDING,
                    started_at=None,
                )
            )
            response = self.run_response(run)
            await self.session.commit()
            return response
        except BaseException:
            await self.session.rollback()
            raise

    async def get_run(self, run_id: int) -> dto.RunResponse:
        return self.run_response(await self.repo.get_run(run_id))

    async def _lock_run_context(self, run_id):
        initial = await self.repo.get_run(run_id)
        if initial.workflow_id is not None:
            workflow = await self.repo.get(Workflow, initial.workflow_id, lock=True)
            if workflow.status != WorkflowStatus.ACTIVE:
                # Idempotent reads of an already committed capture remain possible.
                if await self.repo.get_capture(run_id) is None:
                    raise ExtractionConflict("Workflow is not active")
            if (
                workflow.source_id != initial.source_id
                or workflow.source_snapshot_id != initial.source_snapshot_id
            ):
                raise ExtractionValidationError("Extraction run no longer matches its workflow")
        await self.repo.lock_source(initial.source_id)
        run = await self.repo.get_run(run_id, lock=True)
        snapshot = await self.repo.get_snapshot(run.source_snapshot_id)
        if snapshot.source_id != run.source_id:
            raise ExtractionValidationError("Run and snapshot belong to different sources")
        return run, snapshot

    async def register_capture(
        self, run_id: int, request: dto.CaptureRequest, *, expected_definitions=None
    ):
        """One run accepts one successful capture. FAILED runs may be retried."""
        try:
            run, snapshot = await self._lock_run_context(run_id)
            digest = payload_hash(request)
            existing = await self.repo.get_capture(run_id)
            if existing is not None:
                if existing.capture_key != request.capture_key or existing.payload_hash != digest:
                    raise ExtractionConflict(
                        "Run already captured; retry with the identical key and payload"
                    )
                response = dto.CaptureResponse.model_validate(existing.result_json)
                await self.session.commit()
                return response
            key_owner = await self.repo.capture_for_key(request.capture_key)
            if key_owner is not None:
                raise ExtractionConflict("capture_key already belongs to a different run")
            await self._source(run.source_id)
            if run.status not in {ExtractionRunStatus.PENDING, ExtractionRunStatus.FAILED}:
                raise ExtractionConflict(f"Cannot capture a {run.status} run")
            if expected_definitions is not None:
                current = await self.repo.definitions(run.source_id)
                if definitions_fingerprint(current) != expected_definitions:
                    raise ExtractionConflict(
                        "Extraction definitions changed during execution; retry"
                    )
            run.status = ExtractionRunStatus.RUNNING
            run.started_at = utc_now()
            run.finished_at = None
            run.error_message = None
            await self.session.flush()
            try:
                async with self.session.begin_nested():
                    response = await CaptureWriter(self.repo, run, snapshot).write(request)
                    run.status = response.status
                    run.finished_at = utc_now()
                    await self.repo.add(
                        ExtractionCapture(
                            run_id=run.id,
                            capture_key=request.capture_key,
                            payload_hash=digest,
                            result_json=response.model_dump(mode="json"),
                        )
                    )
                await self.session.commit()
                return response
            except Exception as error:
                # The savepoint removes all evidence/definitions/bindings. The
                # original run stays accessible and receives durable failure state.
                run = await self.repo.get_run(run_id, lock=True)
                run.status = ExtractionRunStatus.FAILED
                run.finished_at = utc_now()
                public_message = (
                    str(error)
                    if isinstance(error, (ExtractionError, SourceConflict))
                    else "Capture failed while persisting evidence"
                )
                run.error_message = public_message[:2000]
                await self.session.commit()
                if isinstance(error, IntegrityError):
                    raise ExtractionConflict(
                        "Capture conflicts with existing evidence or a concurrent commit"
                    ) from error
                if isinstance(error, SourceConflict):
                    raise ExtractionConflict(str(error)) from error
                raise
        except BaseException:
            await self.session.rollback()
            raise

    async def register_token_class(self, request: dto.TokenClassRequest) -> dto.TokenClassRequest:
        try:
            row = await self.repo.get_or_create(
                TokenClass, {"id": request.id}, request.model_dump(exclude={"id"})
            )
            if any(getattr(row, k) != v for k, v in request.model_dump().items()):
                raise ExtractionConflict("Token class already exists with a different definition")
            response = dto.TokenClassRequest.model_validate(row.model_dump())
            await self.session.commit()
            return response
        except BaseException:
            await self.session.rollback()
            raise

    async def resolve_observation_object(
        self, observation_id: int, business_object_id: int
    ) -> dto.ObservationResponse:
        try:
            initial = await self.repo.get(FieldObservation, observation_id)
            source_field = await self.repo.get(
                SourceFieldTracking, initial.source_field_tracking_id
            )
            await self._source(source_field.source_id)
            observation = await self.repo.get(FieldObservation, observation_id, lock=True)
            if observation.status in {ObservationStatus.REJECTED, ObservationStatus.SUPERSEDED}:
                raise ExtractionConflict("Cannot resolve rejected or superseded evidence")
            if observation.business_object_id is not None:
                if observation.business_object_id != business_object_id:
                    raise ExtractionConflict("Observation is already bound to another object")
                response = dto.ObservationResponse.model_validate(observation)
                await self.session.commit()
                return response
            run = await self.repo.get_run(observation.extraction_run_id)
            snapshot = await self.repo.get_snapshot(run.source_snapshot_id)
            if run.source_id != source_field.source_id or snapshot.source_id != run.source_id:
                raise ExtractionValidationError("Observation/run/source mismatch")
            if observation.scope_instance_id is not None:
                instance = await self.repo.get(ScopeInstance, observation.scope_instance_id)
                if instance.extraction_run_id != run.id:
                    raise ExtractionValidationError(
                        "Observation scope belongs to another extraction run"
                    )
            value = await self.repo.observation_value(observation)
            if value is None:
                raise ExtractionValidationError("Observation has no capture literal")

            element = await self.repo.get(Element, value.element_id)
            if element.extraction_run_id != run.id:
                raise ExtractionValidationError("Concrete value belongs to another extraction run")
            field = await self.repo.field(source_field.business_entity_field_id)
            if observation.scope_instance_id is not None:
                siblings = await self.repo.bound_siblings(observation.scope_instance_id)
                for sibling in siblings:
                    sibling_field = await self.repo.get(
                        SourceFieldTracking, sibling.source_field_tracking_id
                    )
                    sibling_definition = await self.repo.field(
                        sibling_field.business_entity_field_id
                    )
                    if (
                        sibling_definition.business_entity_id == field.business_entity_id
                        and sibling.business_object_id != business_object_id
                    ):
                        raise ExtractionConflict(
                            "Another field in this occurrence is bound to a different object"
                        )
            slot, tracking = await CaptureWriter(self.repo, run, snapshot).resolve_binding(
                field,
                business_object_id,
                source_field,
            )
            observation.business_object_id = business_object_id
            observation.business_object_field_id = slot.id
            observation.source_object_field_tracking_id = tracking.id
            await self.session.flush()
            await update_tracking_from_observation(self.repo, tracking, observation)
            response = dto.ObservationResponse.model_validate(observation)
            await self.session.commit()
            return response
        except BaseException:
            await self.session.rollback()
            raise

    async def execute(self, run_id: int, capture_key: str) -> dto.CaptureResponse:
        if self.extractor is None:
            raise ExtractionNotConfigured(
                "No SnapshotExtractor is configured; register a capture or configure an adapter"
            )
        try:
            run = await self.repo.get_run(run_id)
            existing = await self.repo.get_capture(run_id)
            if existing is not None:
                if existing.capture_key != capture_key:
                    raise ExtractionConflict("Run already captured with another key")
                response = dto.CaptureResponse.model_validate(existing.result_json)
                await self.session.commit()
                return response
            if run.status not in {ExtractionRunStatus.PENDING, ExtractionRunStatus.FAILED}:
                raise ExtractionConflict(f"Cannot execute a {run.status} run")
            snapshot = await self.repo.get_snapshot(run.source_snapshot_id)
            definitions = await self.repo.definitions(run.source_id)
            # Validate DB JSON before parser I/O. Legacy/invalid definitions require
            # rediscovery; do not guess text or silently omit those fields.
            known_definitions = ExtractionDefinitions.from_rows(*definitions)
            fingerprint = definitions_fingerprint(definitions)
            if any(s.rule.extraction.type == "pageUrl" for s in known_definitions.selectors):
                if snapshot.page_url is None:
                    raise ExtractionConflict("pageUrl execution requires a recorded snapshot URL")
            snapshot_input = type(snapshot).model_validate(snapshot.model_dump())
            # Keep authoritative copies separate: an adapter must not be able to
            # modify the definitions against which its returned capture is checked.
            adapter_definitions = deepcopy(known_definitions)
            await self.session.rollback()
            try:
                capture = await self.extractor.extract(
                    snapshot_input, adapter_definitions, capture_key=capture_key
                )
                if adapter_definitions != known_definitions:
                    raise ExtractionValidationError("Adapter mutated its extraction definitions")
                capture = dto.CaptureRequest.model_validate(
                    capture.model_dump(mode="json")
                    if isinstance(capture, dto.CaptureRequest)
                    else capture
                )
                if capture.capture_key != capture_key:
                    raise ExtractionValidationError("Adapter returned the wrong capture key")
                if any(v.confirmed_by_human for v in capture.values):
                    raise ExtractionValidationError(
                        "Automatic adapters cannot assert human confirmation"
                    )
                # Execution may apply existing recipes, but cannot rewrite them.
                active = {s.name: s for s in known_definitions.scopes}
                active_by_id = {s.id: s for s in known_definitions.scopes}
                requested_scopes = {s.client_key: s for s in capture.scopes}
                for scope in capture.scopes:
                    known = active.get(scope.name)
                    if known is None or (
                        scope.selector.type,
                        scope.selector.value,
                        scope.business_entity_id,
                    ) != (known.selector_type, known.selector_string, known.business_entity_id):
                        raise ExtractionValidationError(
                            "Adapter attempted to change an extraction definition"
                        )
                    parent_name = (
                        requested_scopes[scope.parent_client_key].name
                        if scope.parent_client_key
                        else None
                    )
                    expected_parent = (
                        active_by_id[known.parent_scope_id].name if known.parent_scope_id else None
                    )
                    if parent_name != expected_parent:
                        raise ExtractionValidationError(
                            "Adapter attempted to change scope parentage"
                        )
                    # These are annotations of the existing recipe, not a new discovery.
                    scope.selector.confidence = known.confidence_score
                    scope.selector.discovered_by = known.discovered_by
                registered_fields = {
                    (active_by_id[s.scope_id].name, s.business_entity_field_id)
                    for s in known_definitions.selectors
                }
                instances = {i.client_key: i for i in capture.scope_instances}
                for value in capture.values:
                    instance = instances[value.scope_instance_client_key]
                    scope_name = requested_scopes[instance.scope_client_key].name
                    if (scope_name, value.business_entity_field_id) not in registered_fields:
                        raise ExtractionValidationError("Adapter field has no registered recipe")
                    if value.discovered_by == DiscoveryMethod.MANUAL:
                        raise ExtractionValidationError(
                            "Automatic adapters cannot claim manual discovery"
                        )
                if any(v.rule is not None for v in capture.values):
                    raise ExtractionValidationError(
                        "Execution adapters must omit field recipe updates"
                    )
            except Exception as error:
                await self.fail_run(
                    run_id,
                    str(error)
                    if isinstance(error, ExtractionError)
                    else "Snapshot extraction adapter failed",
                )
                raise
            return await self.register_capture(run_id, capture, expected_definitions=fingerprint)
        except BaseException:
            await self.session.rollback()
            raise

    async def fail_run(self, run_id: int, message: str) -> None:
        run, _ = await self._lock_run_context(run_id)
        if run.status in {ExtractionRunStatus.PENDING, ExtractionRunStatus.FAILED}:
            run.started_at = utc_now()
            run.finished_at = utc_now()
            run.status = ExtractionRunStatus.FAILED
            run.error_message = message[:2000]
        await self.session.commit()

    async def get_observation(self, observation_id: int) -> dto.ObservationEvidenceResponse:
        observation = await self.repo.get(FieldObservation, observation_id)
        values = await self.repo.observation_values(observation)
        return dto.ObservationEvidenceResponse(
            **observation.model_dump(),
            concrete_values=[dto.CapturedLiteralResponse.model_validate(value) for value in values],
        )

    async def get_capture(self, run_id: int) -> dto.CaptureResponse:
        await self.repo.get_run(run_id)
        capture = await self.repo.get_capture(run_id)
        if capture is None:
            from extraction.exceptions import ExtractionNotFound

            raise ExtractionNotFound("This run has no committed capture")
        return dto.CaptureResponse.model_validate(capture.result_json)
