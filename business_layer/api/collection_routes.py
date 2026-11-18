"""Collections use the existing /business API and transaction/session dependencies."""

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import AwareDatetime

from business_layer.api.dependencies import CollectionsServiceDep
from business_layer.schemas.collections import (
    CollectionCreate,
    CollectionInsert,
    CollectionItemHistory,
    CollectionItemsRead,
    CollectionMutation,
    CollectionPatch,
    CollectionRead,
    CollectionReorder,
    CollectionReplace,
)

router = APIRouter(prefix="/business", tags=["business collections"])
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=500)]


@router.post("/object-fields/{field_id}/collection", response_model=CollectionRead, status_code=201)
async def create_collection(
    field_id: int, payload: CollectionCreate, service: CollectionsServiceDep
):
    return await service.create_collection(field_id, **payload.model_dump())


@router.get("/collections/{collection_id}", response_model=CollectionRead)
async def get_collection(
    collection_id: int,
    service: CollectionsServiceDep,
    at: AwareDatetime | None = None,
    known_at: AwareDatetime | None = None,
):
    return await service.get_collection(collection_id, at=at, known_at=known_at)


@router.get("/collections/{collection_id}/items", response_model=CollectionItemsRead)
async def list_items(
    collection_id: int,
    service: CollectionsServiceDep,
    offset: Offset = 0,
    limit: Limit = 100,
    at: AwareDatetime | None = None,
    known_at: AwareDatetime | None = None,
):
    return await service.list_collection_items(
        collection_id, offset=offset, limit=limit, at=at, known_at=known_at
    )


@router.get(
    "/collections/{collection_id}/items/{item_id}/history",
    response_model=list[CollectionItemHistory],
)
async def item_history(
    collection_id: int,
    item_id: int,
    service: CollectionsServiceDep,
    offset: Offset = 0,
    limit: Limit = 100,
    at: AwareDatetime | None = None,
    known_at: AwareDatetime | None = None,
):
    return await service.item_history(
        collection_id, item_id, offset=offset, limit=limit, at=at, known_at=known_at
    )


@router.post("/collections/{collection_id}/items", response_model=CollectionRead, status_code=201)
async def insert_item(
    collection_id: int, payload: CollectionInsert, service: CollectionsServiceDep
):
    options = payload.model_dump()
    value, position = options.pop("value"), options.pop("position")
    if position is None:
        return await service.append_item(collection_id, value, **options)
    return await service.insert_item(collection_id, position, value, **options)


@router.patch("/collections/{collection_id}/items/{item_id}", response_model=CollectionRead)
async def update_item(
    collection_id: int, item_id: int, payload: CollectionPatch, service: CollectionsServiceDep
):
    options = {"expected_revision": payload.expected_revision, "effective_at": payload.effective_at}
    if "position" in payload.model_fields_set:
        return await service.move_item(collection_id, item_id, payload.position, **options)
    return await service.set_item_value(collection_id, item_id, payload.value, **options)


@router.delete("/collections/{collection_id}/items/{item_id}", response_model=CollectionRead)
async def remove_item(
    collection_id: int, item_id: int, payload: CollectionMutation, service: CollectionsServiceDep
):
    return await service.remove_item(collection_id, item_id, **payload.model_dump())


@router.post("/collections/{collection_id}/items/{item_id}/restore", response_model=CollectionRead)
async def restore_item(
    collection_id: int, item_id: int, payload: CollectionInsert, service: CollectionsServiceDep
):
    return await service.restore_item(collection_id, item_id, **payload.model_dump())


@router.post("/collections/{collection_id}/reorder", response_model=CollectionRead)
async def reorder_items(
    collection_id: int, payload: CollectionReorder, service: CollectionsServiceDep
):
    return await service.reorder_items(collection_id, **payload.model_dump())


@router.put("/collections/{collection_id}/items", response_model=CollectionRead)
async def replace_items(
    collection_id: int, payload: CollectionReplace, service: CollectionsServiceDep
):
    return await service.replace_collection(collection_id, **payload.model_dump())


@router.delete("/collections/{collection_id}/items", response_model=CollectionRead)
async def clear_items(
    collection_id: int, payload: CollectionMutation, service: CollectionsServiceDep
):
    return await service.clear_collection(collection_id, **payload.model_dump())
