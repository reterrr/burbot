from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from extraction.api.dependencies import ExtractionServiceDep
from extraction.schemas import api as dto
from extraction.schemas import capture as capture_dto

router = APIRouter(
    prefix="/extractions",
    tags=["extractions"],
    responses={
        404: {"description": "Workflow or extraction run not found"},
        409: {"description": "Workflow/source state conflicts with extraction"},
        422: {"description": "Extraction evidence is invalid"},
    },
)
PositiveId = Annotated[int, Path(gt=0, le=9223372036854775807)]


@router.post("", status_code=status.HTTP_201_CREATED, deprecated=True)
async def create_pending_run_alias(
    request: capture_dto.CreateRunRequest,
    service: ExtractionServiceDep,
) -> capture_dto.RunResponse:
    """Deprecated alias for POST /extraction/runs, followed by /runs/{id}/capture.

    The retired workflow/field_observations payload is no longer accepted: it
    cannot describe a reusable recipe or concrete record scope.
    """
    return await service.create_run(request)


@router.get("")
async def list_extraction_runs(
    query: Annotated[dto.ExtractionRunListRequest, Query()],
    service: ExtractionServiceDep,
) -> dto.ExtractionRunListResponse:
    return await service.list_extraction_runs(
        query,
        workflow_id=query.workflow_id,
        source_id=query.source_id,
    )


@router.get("/{run_id}")
async def get_extraction_run(
    run_id: PositiveId,
    service: ExtractionServiceDep,
) -> dto.ExtractionRunResponse:
    return await service.get_extraction_run(run_id)


capture_router = APIRouter(
    prefix="/extraction",
    tags=["extraction"],
    responses={
        404: {"description": "Resource not found"},
        409: {"description": "Conflicting capture or source state"},
        422: {"description": "Invalid extraction graph or business binding"},
    },
)


@capture_router.post("/runs", status_code=status.HTTP_201_CREATED)
async def create_snapshot_run(
    request: capture_dto.CreateRunRequest, service: ExtractionServiceDep
) -> capture_dto.RunResponse:
    return await service.create_run(request)


@capture_router.get("/runs/{run_id}")
async def get_snapshot_run(
    run_id: PositiveId, service: ExtractionServiceDep
) -> capture_dto.RunResponse:
    return await service.get_run(run_id)


@capture_router.post("/runs/{run_id}/capture")
async def register_capture(
    run_id: PositiveId, request: capture_dto.CaptureRequest, service: ExtractionServiceDep
) -> capture_dto.CaptureResponse:
    return await service.register_capture(run_id, request)


@capture_router.post("/runs/{run_id}/execute")
async def execute_run(
    run_id: PositiveId, request: capture_dto.ExecuteRequest, service: ExtractionServiceDep
) -> capture_dto.CaptureResponse:
    return await service.execute(run_id, request.capture_key)


@capture_router.post("/observations/{observation_id}/resolve-object")
async def resolve_object(
    observation_id: PositiveId,
    request: capture_dto.ResolveObjectRequest,
    service: ExtractionServiceDep,
) -> capture_dto.ObservationResponse:
    return await service.resolve_observation_object(observation_id, request.business_object_id)


@capture_router.post("/token-classes", status_code=status.HTTP_201_CREATED)
async def register_token_class(
    request: capture_dto.TokenClassRequest, service: ExtractionServiceDep
) -> capture_dto.TokenClassRequest:
    return await service.register_token_class(request)


@capture_router.get("/observations/{observation_id}")
async def get_observation(
    observation_id: PositiveId,
    service: ExtractionServiceDep,
) -> capture_dto.ObservationEvidenceResponse:
    return await service.get_observation(observation_id)


@capture_router.get("/runs/{run_id}/capture")
async def get_capture(
    run_id: PositiveId, service: ExtractionServiceDep
) -> capture_dto.CaptureResponse:
    return await service.get_capture(run_id)
