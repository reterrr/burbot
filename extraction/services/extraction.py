from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from business_layer.schemas.models import BusinessObject, BusinessObjectField
from extraction.exceptions import (
    ExtractionConflict,
    ExtractionNotFound,
    ExtractionValidationError,
)
from extraction.schemas import api as dto
from extraction.schemas import capture as capture_dto
from extraction.schemas.evidence import TokenClass
from extraction.schemas.models import (
    ConcreteValue,
    ExtractionRun,
    ExtractionRunStatus,
    FieldObservation,
    utc_now,
)
from extraction.services.adapters import SnapshotExtractor
from extraction.services.capture import CaptureService
from sources.schemas.enums import SourceState
from sources.schemas.models import (
    Source,
    SourceFieldTracking,
    SourceObjectFieldTracking,
)
from tasks.schemas.models import Workflow, WorkflowStatus


@dataclass(slots=True)
class _EvidenceValue:
    snapshot_id: int
    value: dto.CreateExtractionConcreteValueRequest


@dataclass(slots=True)
class _EvidenceGroup:
    object_id: int
    object_field_id: int
    values: list[_EvidenceValue] = field(default_factory=list)


@dataclass(slots=True)
class _PreparedObservation:
    object_id: int
    object_field_id: int
    source_field_tracking_id: int
    tracking_version_id: int
    values: list[_EvidenceValue]


class ExtractionService:
    """Layer 3 service for persisting extraction evidence.

    The browser/extension is responsible for selecting evidence from a rendered
    source. This service validates that evidence against the current workflow and
    Layer 2 tracking configuration and persists provenance atomically.

    It deliberately does not write ``BusinessObjectFieldValue``. An observation is
    evidence, not canonical business state.
    """

    def __init__(self, session: AsyncSession, extractor: SnapshotExtractor | None = None) -> None:
        self._session = session
        self.capture = CaptureService(session, extractor)

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        try:
            yield
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            constraint = self._constraint_name(error)
            if constraint == "uq_field_observations_run_object_field":
                raise ExtractionConflict(
                    "This extraction run already contains an observation for that object field"
                ) from error
            if constraint == "uq_extraction_values_observation_index":
                raise ExtractionConflict("Concrete evidence was inserted concurrently") from error
            raise
        except BaseException:
            await self._session.rollback()
            raise

    @staticmethod
    def _constraint_name(error: IntegrityError) -> str | None:
        original = error.orig
        diagnostic = getattr(original, "diag", None) or getattr(original, "__cause__", None)
        return getattr(diagnostic, "constraint_name", None)

    async def _get_workflow(
        self,
        workflow_id: int,
        *,
        for_update: bool = False,
    ) -> Workflow:
        statement = select(Workflow).where(col(Workflow.id) == workflow_id)
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        workflow = await self._session.scalar(statement)
        if workflow is None:
            raise ExtractionNotFound(f"Workflow {workflow_id} does not exist")
        return workflow

    async def _get_source(
        self,
        source_id: int,
        *,
        for_update: bool = False,
    ) -> Source:
        statement = select(Source).where(col(Source.id) == source_id)
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        source = await self._session.scalar(statement)
        if source is None:
            raise ExtractionValidationError(
                f"Workflow references source {source_id}, but that source does not exist"
            )
        return source

    async def _get_object(self, object_id: int) -> BusinessObject:
        obj = await self._session.scalar(
            select(BusinessObject)
            .where(col(BusinessObject.id) == object_id)
            .with_for_update(read=True)
        )
        if obj is None:
            raise ExtractionValidationError(f"Business object {object_id} does not exist")
        return obj

    async def _get_object_field(self, object_field_id: int) -> BusinessObjectField:
        object_field = await self._session.scalar(
            select(BusinessObjectField)
            .where(col(BusinessObjectField.id) == object_field_id)
            .with_for_update(read=True)
        )
        if object_field is None:
            raise ExtractionValidationError(
                f"Business object field {object_field_id} does not exist"
            )
        return object_field

    async def _current_tracking(
        self,
        source_id: int,
        object_field_id: int,
    ) -> SourceObjectFieldTracking:
        tracking = await self._session.scalar(
            select(SourceObjectFieldTracking)
            .join(
                SourceFieldTracking,
                col(SourceObjectFieldTracking.source_field_tracking_id)
                == col(SourceFieldTracking.id),
            )
            .where(
                col(SourceFieldTracking.source_id) == source_id,
                col(SourceObjectFieldTracking.business_object_field_id) == object_field_id,
                col(SourceObjectFieldTracking.valid_to).is_(None),
                col(SourceObjectFieldTracking.tracking_enabled).is_(True),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if tracking is None:
            raise ExtractionValidationError(
                f"Business object field {object_field_id} is not currently tracked "
                f"for source {source_id}"
            )
        return tracking

    @staticmethod
    def _group_request(
        request: dto.CreateExtractionRunRequest,
        snapshot_id: int,
    ) -> dict[int, _EvidenceGroup]:
        groups: dict[int, _EvidenceGroup] = {}

        for observation_request in request.field_observations:
            for evidence in observation_request.concrete_values:
                if evidence.snapshot_id != snapshot_id:
                    raise ExtractionValidationError(
                        "Every submitted evidence snapshot must match the workflow snapshot "
                        f"{snapshot_id}; received {evidence.snapshot_id}"
                    )

                for value in evidence.values:
                    existing = groups.get(value.object_field_id)
                    if existing is None:
                        existing = _EvidenceGroup(
                            object_id=observation_request.object_id,
                            object_field_id=value.object_field_id,
                        )
                        groups[value.object_field_id] = existing
                    elif existing.object_id != observation_request.object_id:
                        raise ExtractionValidationError(
                            f"Object field {value.object_field_id} was submitted for multiple "
                            "business objects"
                        )

                    existing.values.append(
                        _EvidenceValue(snapshot_id=evidence.snapshot_id, value=value)
                    )

        if not groups:
            raise ExtractionValidationError("At least one concrete value is required")

        return groups

    async def _prepare_observations(
        self,
        workflow: Workflow,
        request: dto.CreateExtractionRunRequest,
    ) -> list[_PreparedObservation]:
        groups = self._group_request(request, workflow.source_snapshot_id)
        checked_objects: set[int] = set()
        prepared: list[_PreparedObservation] = []

        for group in groups.values():
            if group.object_id not in checked_objects:
                await self._get_object(group.object_id)
                checked_objects.add(group.object_id)

            object_field = await self._get_object_field(group.object_field_id)
            if object_field.business_object_id != group.object_id:
                raise ExtractionValidationError(
                    f"Business object field {group.object_field_id} belongs to object "
                    f"{object_field.business_object_id}, not object {group.object_id}"
                )

            tracking = await self._current_tracking(
                workflow.source_id,
                group.object_field_id,
            )
            if tracking.id is None:
                raise RuntimeError("Tracking version has no id")

            prepared.append(
                _PreparedObservation(
                    object_id=group.object_id,
                    object_field_id=group.object_field_id,
                    source_field_tracking_id=tracking.source_field_tracking_id,
                    tracking_version_id=tracking.id,
                    values=group.values,
                )
            )

        return prepared

    async def create_extraction_run(
        self,
        request: dto.CreateExtractionRunRequest,
    ) -> dto.ExtractionRunResponse:
        """Persist one complete extraction submission atomically."""
        async with self._transaction():
            workflow = await self._get_workflow(request.workflow_id, for_update=True)
            if workflow.status != WorkflowStatus.ACTIVE:
                raise ExtractionConflict(
                    f"Workflow {workflow.id} is {workflow.status}; only active workflows "
                    "accept new extraction evidence"
                )

            # Layer 2 serializes tracking mutations by locking the source row.
            # Take the same lock before resolving exact tracking versions so an
            # observation can never race a version rollover or source archive.
            source = await self._get_source(workflow.source_id, for_update=True)
            if source.state == SourceState.ARCHIVED:
                raise ExtractionConflict(f"Source {source.id} is archived")

            prepared = await self._prepare_observations(workflow, request)
            for token_id in {
                item.value.token_class_id for group in prepared for item in group.values
            }:
                await self.capture.repo.get_or_create(
                    TokenClass, {"id": token_id}, {"name": token_id}
                )
            now = utc_now()
            run = ExtractionRun(
                workflow_id=workflow.id,
                source_id=workflow.source_id,
                source_snapshot_id=workflow.source_snapshot_id,
                status=ExtractionRunStatus.RUNNING,
                started_at=now,
            )
            self._session.add(run)
            await self._session.flush()
            if run.id is None:
                raise RuntimeError("Extraction run has no id after flush")

            for item in prepared:
                observation = FieldObservation(
                    extraction_run_id=run.id,
                    source_field_tracking_id=item.source_field_tracking_id,
                    source_object_field_tracking_id=item.tracking_version_id,
                    business_object_id=item.object_id,
                    business_object_field_id=item.object_field_id,
                    observed_at=now,
                )
                self._session.add(observation)
                await self._session.flush()
                if observation.id is None:
                    raise RuntimeError("Field observation has no id after flush")

                for value_index, evidence_value in enumerate(item.values):
                    value = evidence_value.value
                    self._session.add(
                        ConcreteValue(
                            field_observation_id=observation.id,
                            source_snapshot_id=evidence_value.snapshot_id,
                            raw_value=value.concrete_value,
                            char_start=value.char_start,
                            char_end=value.char_end,
                            token_class_id=value.token_class_id,
                            value_index=value_index,
                        )
                    )

            await self._session.flush()
            run.status = ExtractionRunStatus.COMPLETED
            run.finished_at = utc_now()
            self._session.add(run)
            await self._session.flush()
            result = await self._run_response(run)

        return result

    async def _get_run(self, run_id: int) -> ExtractionRun:
        run = await self._session.get(ExtractionRun, run_id)
        if run is None:
            raise ExtractionNotFound(f"Extraction run {run_id} does not exist")
        return run

    @staticmethod
    def _run_summary(run: ExtractionRun) -> dto.ExtractionRunSummary:
        return dto.ExtractionRunSummary.model_validate(run)

    async def _run_response(self, run: ExtractionRun) -> dto.ExtractionRunResponse:
        observations = list(
            await self._session.scalars(
                select(FieldObservation)
                .where(col(FieldObservation.extraction_run_id) == run.id)
                .order_by(col(FieldObservation.id))
            )
        )
        observation_ids = [row.id for row in observations if row.id is not None]
        values_by_observation: dict[int, list[ConcreteValue]] = {
            observation_id: [] for observation_id in observation_ids
        }

        capture_value_owners = {
            observation.concrete_value_id: observation.id
            for observation in observations
            if observation.concrete_value_id is not None
        }
        if observation_ids:
            values = await self._session.scalars(
                select(ConcreteValue)
                .where(
                    or_(
                        col(ConcreteValue.field_observation_id).in_(observation_ids),
                        col(ConcreteValue.id).in_(capture_value_owners),
                    )
                )
                .order_by(
                    col(ConcreteValue.field_observation_id),
                    col(ConcreteValue.value_index),
                    col(ConcreteValue.id),
                )
            )
            for value in values:
                owner = value.field_observation_id or capture_value_owners[value.id]
                values_by_observation[owner].append(value)

        field_observations: list[dto.FieldObservationResponse] = []
        for observation in observations:
            if observation.id is None:
                continue
            field_observations.append(
                dto.FieldObservationResponse(
                    id=observation.id,
                    business_object_id=observation.business_object_id,
                    business_object_field_id=observation.business_object_field_id,
                    tracking_version_id=observation.source_object_field_tracking_id,
                    observed_at=observation.observed_at,
                    concrete_values=[
                        dto.ConcreteValueResponse(
                            id=value.id,
                            snapshot_id=value.source_snapshot_id,
                            concrete_value=value.raw_value,
                            char_start=value.char_start,
                            char_end=value.char_end,
                            token_class_id=value.token_class_id,
                            value_index=value.value_index,
                        )
                        for value in values_by_observation[observation.id]
                        if value.id is not None
                    ],
                )
            )

        summary = self._run_summary(run)
        return dto.ExtractionRunResponse(
            **summary.model_dump(),
            field_observations=field_observations,
        )

    async def get_extraction_run(self, run_id: int) -> dto.ExtractionRunResponse:
        return await self._run_response(await self._get_run(run_id))

    async def list_extraction_runs(
        self,
        query: dto.Pagination,
        *,
        workflow_id: int | None = None,
        source_id: int | None = None,
    ) -> dto.ExtractionRunListResponse:
        statement = select(ExtractionRun)
        if workflow_id is not None:
            statement = statement.where(col(ExtractionRun.workflow_id) == workflow_id)
        if source_id is not None:
            statement = statement.where(col(ExtractionRun.source_id) == source_id)

        total = await self._session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        runs = await self._session.scalars(
            statement.order_by(col(ExtractionRun.id).desc()).offset(query.offset).limit(query.limit)
        )
        return dto.ExtractionRunListResponse(
            items=[self._run_summary(run) for run in runs],
            total=total or 0,
            offset=query.offset,
            limit=query.limit,
        )

    async def create_run(self, request: capture_dto.CreateRunRequest) -> capture_dto.RunResponse:
        return await self.capture.create_run(request)

    async def register_capture(
        self, run_id: int, request: capture_dto.CaptureRequest
    ) -> capture_dto.CaptureResponse:
        return await self.capture.register_capture(run_id, request)

    async def resolve_observation_object(
        self, observation_id: int, business_object_id: int
    ) -> capture_dto.ObservationResponse:
        return await self.capture.resolve_observation_object(observation_id, business_object_id)

    async def execute(self, run_id: int, capture_key: str) -> capture_dto.CaptureResponse:
        return await self.capture.execute(run_id, capture_key)
