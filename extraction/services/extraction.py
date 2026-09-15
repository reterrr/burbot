"""Extraction facade: one capture writer plus read compatibility for historical runs."""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from extraction.exceptions import ExtractionNotFound
from extraction.schemas import api as dto
from extraction.schemas import capture as capture_dto
from extraction.schemas.models import ConcreteValue, ExtractionRun, FieldObservation
from extraction.services.adapters import SnapshotExtractor
from extraction.services.capture import CaptureService


class ExtractionService:
    """Own extraction definitions/evidence through the canonical capture pipeline.

    Historical workflow runs remain readable. Every write is delegated to
    CaptureService; no evidence-only persistence or canonical value writes live here.
    """

    def __init__(self, session: AsyncSession, extractor: SnapshotExtractor | None = None) -> None:
        self._session = session
        self.capture = CaptureService(session, extractor)

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

    async def get_run(self, run_id: int) -> capture_dto.RunResponse:
        return await self.capture.get_run(run_id)

    async def get_capture(self, run_id: int) -> capture_dto.CaptureResponse:
        return await self.capture.get_capture(run_id)

    async def get_observation(self, observation_id: int) -> capture_dto.ObservationEvidenceResponse:
        return await self.capture.get_observation(observation_id)

    async def register_token_class(
        self, request: capture_dto.TokenClassRequest
    ) -> capture_dto.TokenClassRequest:
        return await self.capture.register_token_class(request)
