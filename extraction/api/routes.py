from typing import Annotated

from fastapi import APIRouter, Path, Query, status

from extraction.api.dependencies import ExtractionServiceDep
from extraction.schemas import api as dto


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


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_extraction_run(
    request: dto.CreateExtractionRunRequest,
    service: ExtractionServiceDep,
) -> dto.ExtractionRunResponse:
    """Persist browser/user supplied evidence for the workflow's source snapshot."""
    return await service.create_extraction_run(request)


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
