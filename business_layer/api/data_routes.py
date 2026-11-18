"""HTTP operations for concrete business objects and value history."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Query, Response, status

from business_layer.api.dependencies import DataServiceDep
from business_layer.schemas.models.dtos import (
    AssignFieldValuesRequest,
    BusinessObjectFieldValueRead,
    BusinessObjectRead,
    CreateObjectRequest,
    CreateObjectResponse,
)

router = APIRouter(prefix="/business", tags=["business data"])


@router.post(
    "/entities/{entity_id}/objects",
    response_model=CreateObjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_object(
    entity_id: int,
    service: DataServiceDep,
    payload: Annotated[CreateObjectRequest | None, Body()] = None,
) -> CreateObjectResponse:
    return await service.create_object(entity_id, payload.values if payload else None)


@router.get(
    "/entities/{entity_id}/objects",
    response_model=list[BusinessObjectRead],
)
async def list_objects(
    entity_id: int,
    service: DataServiceDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    include_archived: bool = False,
    at: datetime | None = None,
    known_at: datetime | None = None,
) -> list[BusinessObjectRead]:
    return await service.list_objects(
        entity_id,
        offset=offset,
        limit=limit,
        include_archived=include_archived,
        at=at,
        known_at=known_at,
    )


@router.get(
    "/objects/{object_id}",
    response_model=BusinessObjectRead,
)
async def get_object(
    object_id: int,
    service: DataServiceDep,
    at: datetime | None = None,
    known_at: datetime | None = None,
) -> BusinessObjectRead:
    return await service.get_object(object_id, at=at, known_at=known_at)


@router.patch(
    "/objects/{object_id}/values",
    response_model=BusinessObjectRead,
)
async def assign_object_field_values(
    object_id: int,
    payload: AssignFieldValuesRequest,
    service: DataServiceDep,
) -> BusinessObjectRead:
    return await service.assign_object_fields_values(
        object_id,
        payload.field_values,
        effective_at=payload.effective_at,
        expected_value_ids=payload.expected_value_ids,
        expected_collection_revisions=payload.expected_collection_revisions,
    )


@router.delete(
    "/objects/{object_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_object(
    object_id: int,
    service: DataServiceDep,
) -> Response:
    await service.delete_object(object_id)

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.get(
    "/object-fields/{object_field_id}/history",
    response_model=list[BusinessObjectFieldValueRead],
)
async def get_object_field_history(
    object_field_id: int,
    service: DataServiceDep,
    at: datetime | None = None,
    known_at: datetime | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[BusinessObjectFieldValueRead]:
    return await service.get_object_field_value_history(
        object_field_id,
        at=at,
        known_at=known_at,
        offset=offset,
        limit=limit,
    )


@router.post("/objects/{object_id}/sync-fields", response_model=CreateObjectResponse)
async def sync_object_fields(object_id: int, service: DataServiceDep):
    return await service.sync_object_fields(object_id)


@router.post("/objects/{object_id}/archive", response_model=BusinessObjectRead)
async def archive_object(object_id: int, service: DataServiceDep):
    return await service.archive_object(object_id)


@router.post("/objects/{object_id}/restore", response_model=BusinessObjectRead)
async def restore_object(object_id: int, service: DataServiceDep):
    return await service.restore_object(object_id)
