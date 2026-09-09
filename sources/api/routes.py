"""Layer 2 HTTP endpoints, backed directly by SourcesService."""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Response, status

from sources.api.dependencies import SourcesServiceDep
from sources.schemas import api as dto

router = APIRouter(
    prefix="/sources",
    tags=["sources"],
    responses={
        404: {"description": "Source or related resource not found"},
        409: {"description": "Duplicate identity or conflicting state"},
    },
)
PositiveId = Annotated[int, Path(gt=0, le=9223372036854775807)]
Pagination = Annotated[dto.Pagination, Query()]


@router.post("/stored-files", status_code=status.HTTP_201_CREATED)
async def register_file(
    request: dto.StoredFileCreateRequest, service: SourcesServiceDep
) -> dto.StoredFileResponse:
    """Register a storage descriptor; file bytes are stored by the caller."""
    return await service.register_file(request)


@router.get("/stored-files/{file_id}")
async def get_file(file_id: PositiveId, service: SourcesServiceDep) -> dto.StoredFileResponse:
    return await service.get_file(file_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_source(
    request: dto.SourceCreateRequest, service: SourcesServiceDep
) -> dto.SourceResponse:
    """Register an UNDISCOVERED source without starting acquisition or Temporal."""
    return await service.create_source(request)


@router.get("")
async def list_sources(
    query: Annotated[dto.SourceListRequest, Query()], service: SourcesServiceDep
) -> dto.SourceListResponse:
    return await service.list_sources(query)


@router.get("/{source_id}")
async def get_source(source_id: PositiveId, service: SourcesServiceDep) -> dto.SourceResponse:
    return await service.get_source(source_id)


@router.patch("/{source_id}")
async def update_source(
    source_id: PositiveId, request: dto.SourceUpdateRequest, service: SourcesServiceDep
) -> dto.SourceResponse:
    return await service.update_source(source_id, request)


@router.put("/{source_id}/state")
async def change_source_state(
    source_id: PositiveId, request: dto.SourceStateChangeRequest, service: SourcesServiceDep
) -> dto.SourceResponse:
    return await service.change_state(source_id, request)


@router.get("/{source_id}/state-history")
async def get_state_history(
    source_id: PositiveId, query: Pagination, service: SourcesServiceDep
) -> dto.SourceStateHistoryListResponse:
    return await service.get_state_history(source_id, query)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_source(source_id: PositiveId, service: SourcesServiceDep) -> Response:
    """Retain identity/history and disable configured scheduling and tracking."""
    await service.archive_source(source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{source_id}/metadata")
async def get_metadata(
    source_id: PositiveId, service: SourcesServiceDep
) -> dto.SourceMetadataResponse:
    return await service.get_metadata(source_id)


@router.put("/{source_id}/metadata")
async def set_metadata(
    source_id: PositiveId, request: dto.SourceMetadataWrite, service: SourcesServiceDep
) -> dto.SourceMetadataResponse:
    return await service.set_metadata(source_id, request)


@router.get("/{source_id}/check-schedule")
async def get_schedule(
    source_id: PositiveId, service: SourcesServiceDep
) -> dto.SourceCheckScheduleResponse:
    return await service.get_schedule(source_id)


@router.put("/{source_id}/check-schedule")
async def set_schedule(
    source_id: PositiveId, request: dto.SourceCheckScheduleWrite, service: SourcesServiceDep
) -> dto.SourceCheckScheduleResponse:
    """Store source-level cadence. This endpoint does not launch a scheduler."""
    return await service.set_schedule(source_id, request)


@router.post("/{source_id}/warnings", status_code=status.HTTP_201_CREATED)
async def add_warning(
    source_id: PositiveId, request: dto.SourceWarningCreate, service: SourcesServiceDep
) -> dto.SourceWarningResponse:
    return await service.add_warning(source_id, request)


@router.get("/{source_id}/warnings")
async def list_warnings(
    source_id: PositiveId,
    query: Annotated[dto.SourceWarningListRequest, Query()],
    service: SourcesServiceDep,
) -> dto.Page[dto.SourceWarningResponse]:
    return await service.list_warnings(source_id, query)


@router.patch("/{source_id}/warnings/{warning_id}")
async def update_warning(
    source_id: PositiveId,
    warning_id: PositiveId,
    request: dto.SourceWarningUpdate,
    service: SourcesServiceDep,
) -> dto.SourceWarningResponse:
    return await service.update_warning(source_id, warning_id, request)


@router.get("/{source_id}/business-entities")
async def list_entities(
    source_id: PositiveId, query: Pagination, service: SourcesServiceDep
) -> dto.Page[dto.SourceBusinessEntityResponse]:
    return await service.list_entities(source_id, query)


@router.put("/{source_id}/business-entities/{entity_id}")
async def link_entity(
    source_id: PositiveId, entity_id: PositiveId, service: SourcesServiceDep
) -> dto.SourceBusinessEntityResponse:
    return await service.link_entity(source_id, entity_id)


@router.delete("/{source_id}/business-entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_entity(
    source_id: PositiveId, entity_id: PositiveId, service: SourcesServiceDep
) -> Response:
    await service.unlink_entity(source_id, entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{source_id}/business-objects")
async def list_objects(
    source_id: PositiveId, query: Pagination, service: SourcesServiceDep
) -> dto.Page[dto.SourceBusinessObjectResponse]:
    return await service.list_objects(source_id, query)


@router.put("/{source_id}/business-objects/{object_id}")
async def link_object(
    source_id: PositiveId, object_id: PositiveId, service: SourcesServiceDep
) -> dto.SourceBusinessObjectResponse:
    return await service.link_object(source_id, object_id)


@router.delete("/{source_id}/business-objects/{object_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_object(
    source_id: PositiveId, object_id: PositiveId, service: SourcesServiceDep
) -> Response:
    await service.unlink_object(source_id, object_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{source_id}/field-trackings", status_code=status.HTTP_201_CREATED)
async def create_field_tracking(
    source_id: PositiveId, request: dto.SourceFieldTrackingCreate, service: SourcesServiceDep
) -> dto.SourceFieldTrackingResponse:
    return await service.create_field_tracking(source_id, request)


@router.get("/{source_id}/field-trackings")
async def list_field_trackings(
    source_id: PositiveId, query: Pagination, service: SourcesServiceDep
) -> dto.Page[dto.SourceFieldTrackingResponse]:
    return await service.list_field_trackings(source_id, query)


@router.get("/{source_id}/field-trackings/{tracking_id}")
async def get_field_tracking(
    source_id: PositiveId, tracking_id: PositiveId, service: SourcesServiceDep
) -> dto.SourceFieldTrackingResponse:
    return await service.get_field_tracking(source_id, tracking_id)


@router.patch("/{source_id}/field-trackings/{tracking_id}")
async def update_field_tracking(
    source_id: PositiveId,
    tracking_id: PositiveId,
    request: dto.SourceFieldTrackingUpdate,
    service: SourcesServiceDep,
) -> dto.SourceFieldTrackingResponse:
    return await service.update_field_tracking(source_id, tracking_id, request)


@router.post(
    "/{source_id}/field-trackings/{tracking_id}/object-field-trackings",
    status_code=status.HTTP_201_CREATED,
)
async def create_object_field_tracking(
    source_id: PositiveId,
    tracking_id: PositiveId,
    request: dto.SourceObjectFieldTrackingCreate,
    service: SourcesServiceDep,
) -> dto.SourceObjectFieldTrackingResponse:
    return await service.create_object_field_tracking(source_id, tracking_id, request)


@router.get("/{source_id}/field-trackings/{tracking_id}/object-field-trackings")
async def list_object_field_trackings(
    source_id: PositiveId, tracking_id: PositiveId, query: Pagination, service: SourcesServiceDep
) -> dto.Page[dto.SourceObjectFieldTrackingResponse]:
    return await service.list_object_field_trackings(source_id, tracking_id, query)


@router.get(
    "/{source_id}/field-trackings/{tracking_id}/object-field-trackings/{object_tracking_id}"
)
async def get_object_field_tracking(
    source_id: PositiveId,
    tracking_id: PositiveId,
    object_tracking_id: PositiveId,
    service: SourcesServiceDep,
) -> dto.SourceObjectFieldTrackingResponse:
    return await service.get_object_field_tracking(source_id, tracking_id, object_tracking_id)


@router.patch(
    "/{source_id}/field-trackings/{tracking_id}/object-field-trackings/{object_tracking_id}"
)
async def update_object_field_tracking(
    source_id: PositiveId,
    tracking_id: PositiveId,
    object_tracking_id: PositiveId,
    request: dto.SourceObjectFieldTrackingUpdate,
    service: SourcesServiceDep,
) -> dto.SourceObjectFieldTrackingResponse:
    return await service.update_object_field_tracking(
        source_id, tracking_id, object_tracking_id, request
    )
