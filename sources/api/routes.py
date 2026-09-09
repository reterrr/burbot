from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from sources.api.dependencies import SourcesServiceDep
from sources.schemas.api import (
    Pagination,
    SourceCreateRequest,
    SourceListRequest,
    SourceListResponse,
    SourceResponse,
    SourceStateChangeRequest,
    SourceStateHistoryListResponse,
    SourceUpdateRequest,
)

router = APIRouter(
    prefix="/sources",
    tags=["sources"],
)


SourceId = Annotated[int, Path(gt=0)]
ERRORS = {404: {"description": "Source not found"}, 409: {"description": "Source conflict"}}


@router.post(
    "", response_model=SourceResponse, status_code=status.HTTP_201_CREATED, responses=ERRORS
)
async def create_source(request: SourceCreateRequest, service: SourcesServiceDep) -> SourceResponse:
    """Register a source without starting discovery, fetching, or a workflow."""
    return await service.create_source(request)


@router.get("", response_model=SourceListResponse)
async def list_sources(
    query: Annotated[SourceListRequest, Query()],
    service: SourcesServiceDep,
) -> SourceListResponse:
    return await service.list_sources(query)


@router.get("/{source_id}", response_model=SourceResponse, responses=ERRORS)
async def get_source(source_id: SourceId, service: SourcesServiceDep) -> SourceResponse:
    return await service.get_source(source_id)


@router.patch("/{source_id}", response_model=SourceResponse, responses=ERRORS)
async def update_source(
    source_id: SourceId,
    request: SourceUpdateRequest,
    service: SourcesServiceDep,
) -> SourceResponse:
    """Correct registration details before the first lifecycle transition."""
    return await service.update_source(source_id, request)


@router.put("/{source_id}/state", response_model=SourceResponse, responses=ERRORS)
async def change_source_state(
    source_id: SourceId,
    request: SourceStateChangeRequest,
    service: SourcesServiceDep,
) -> SourceResponse:
    """Check expected_state and atomically record an allowed lifecycle transition."""
    return await service.change_state(source_id, request)


@router.get(
    "/{source_id}/state-history", response_model=SourceStateHistoryListResponse, responses=ERRORS
)
async def get_state_history(
    source_id: SourceId,
    query: Annotated[Pagination, Query()],
    service: SourcesServiceDep,
) -> SourceStateHistoryListResponse:
    return await service.get_state_history(source_id, query)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
async def archive_source(source_id: SourceId, service: SourcesServiceDep) -> Response:
    """Archive a source, retaining its identity and history. Repeated calls are harmless."""
    await service.archive_source(source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
