from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from business_driver.api.dependencies import get_business_session
from business_driver.schemas.api import (
    BusinessEntityCreate,
    BusinessEntityFieldCreate,
    BusinessEntityFieldRead,
    BusinessEntityFieldUpdate,
    BusinessEntityFieldValueRead,
    BusinessEntityFieldValueSet,
    BusinessEntityRead,
    BusinessEntityRelationCreate,
    BusinessEntityRelationRead,
    BusinessEntityRevisionRead,
    BusinessEntityStateField,
    BusinessEntityStatePatch,
    BusinessEntityStateRead,
    BusinessEntityUpdate,
    RelationDirection,
)
from business_driver.services import BusinessService

business_router = APIRouter(
    prefix="/business",
    tags=["Business Knowledge"],
)

SessionDep = Annotated[AsyncSession, Depends(get_business_session)]


def _service(session: AsyncSession) -> BusinessService:
    return BusinessService(session)


@business_router.post(
    "/entities",
    response_model=BusinessEntityRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="createBusinessEntity",
    summary="Create a business entity",
)
async def create_business_entity(
        payload: BusinessEntityCreate,
        session: SessionDep,
) -> BusinessEntityRead:
    entity = await _service(session).create_entity(payload)
    return BusinessEntityRead.model_validate(entity)


@business_router.get(
    "/entities",
    response_model=list[BusinessEntityRead],
    operation_id="listBusinessEntities",
    summary="List business entities",
)
async def list_business_entities(
        session: SessionDep,
        entity_type: str | None = Query(default=None),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
) -> list[BusinessEntityRead]:
    entities = await _service(session).list_entities(
        entity_type=entity_type,
        offset=offset,
        limit=limit,
    )
    return [BusinessEntityRead.model_validate(entity) for entity in entities]


@business_router.get(
    "/entities/{entity_id}",
    response_model=BusinessEntityRead,
    operation_id="getBusinessEntity",
    summary="Get a business entity",
)
async def get_business_entity(
        entity_id: int,
        session: SessionDep,
) -> BusinessEntityRead:
    entity = await _service(session).get_entity(entity_id)
    return BusinessEntityRead.model_validate(entity)


@business_router.patch(
    "/entities/{entity_id}",
    response_model=BusinessEntityRead,
    operation_id="updateBusinessEntity",
    summary="Update a business entity",
)
async def update_business_entity(
        entity_id: int,
        payload: BusinessEntityUpdate,
        session: SessionDep,
) -> BusinessEntityRead:
    entity = await _service(session).update_entity(entity_id, payload)
    return BusinessEntityRead.model_validate(entity)


@business_router.get(
    "/entities/{entity_id}/state",
    response_model=BusinessEntityStateRead,
    operation_id="getBusinessEntityState",
    summary="Get entity fields with their current values",
)
async def get_business_entity_state(
        entity_id: int,
        session: SessionDep,
) -> BusinessEntityStateRead:
    entity, fields = await _service(session).get_state(entity_id)
    return BusinessEntityStateRead(
        entity=BusinessEntityRead.model_validate(entity),
        fields=[
            BusinessEntityStateField(
                field=BusinessEntityFieldRead.model_validate(field),
                current_value=(
                    BusinessEntityFieldValueRead.model_validate(current)
                    if current is not None
                    else None
                ),
            )
            for field, current in fields
        ],
    )


@business_router.patch(
    "/entities/{entity_id}/state",
    response_model=BusinessEntityStateRead,
    operation_id="patchBusinessEntityState",
    summary="Atomically update several current field values",
)
async def patch_business_entity_state(
        entity_id: int,
        payload: BusinessEntityStatePatch,
        session: SessionDep,
) -> BusinessEntityStateRead:
    service = _service(session)
    await service.patch_state(entity_id, payload)
    entity, fields = await service.get_state(entity_id)
    return BusinessEntityStateRead(
        entity=BusinessEntityRead.model_validate(entity),
        fields=[
            BusinessEntityStateField(
                field=BusinessEntityFieldRead.model_validate(field),
                current_value=(
                    BusinessEntityFieldValueRead.model_validate(current)
                    if current is not None
                    else None
                ),
            )
            for field, current in fields
        ],
    )


@business_router.post(
    "/entities/{entity_id}/fields",
    response_model=BusinessEntityFieldRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="createBusinessEntityField",
    summary="Create a field for an entity",
)
async def create_business_entity_field(
        entity_id: int,
        payload: BusinessEntityFieldCreate,
        session: SessionDep,
) -> BusinessEntityFieldRead:
    field = await _service(session).create_field(entity_id, payload)
    return BusinessEntityFieldRead.model_validate(field)


@business_router.get(
    "/entities/{entity_id}/fields",
    response_model=list[BusinessEntityFieldRead],
    operation_id="listBusinessEntityFields",
    summary="List fields of an entity",
)
async def list_business_entity_fields(
        entity_id: int,
        session: SessionDep,
) -> list[BusinessEntityFieldRead]:
    fields = await _service(session).list_fields(entity_id)
    return [BusinessEntityFieldRead.model_validate(field) for field in fields]


@business_router.get(
    "/fields/{field_id}",
    response_model=BusinessEntityFieldRead,
    operation_id="getBusinessEntityField",
    summary="Get one entity field",
)
async def get_business_entity_field(
        field_id: int,
        session: SessionDep,
) -> BusinessEntityFieldRead:
    field = await _service(session).get_field(field_id)
    return BusinessEntityFieldRead.model_validate(field)


@business_router.patch(
    "/fields/{field_id}",
    response_model=BusinessEntityFieldRead,
    operation_id="updateBusinessEntityField",
    summary="Update one entity field",
)
async def update_business_entity_field(
        field_id: int,
        payload: BusinessEntityFieldUpdate,
        session: SessionDep,
) -> BusinessEntityFieldRead:
    field = await _service(session).update_field(field_id, payload)
    return BusinessEntityFieldRead.model_validate(field)


@business_router.delete(
    "/fields/{field_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteBusinessEntityField",
    summary="Soft-delete an entity field",
)
async def delete_business_entity_field(
        field_id: int,
        session: SessionDep,
) -> Response:
    await _service(session).delete_field(field_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@business_router.get(
    "/fields/{field_id}/current-value",
    response_model=BusinessEntityFieldValueRead | None,
    operation_id="getBusinessEntityFieldCurrentValue",
    summary="Get the current accepted value of a field",
)
async def get_business_entity_field_current_value(
        field_id: int,
        session: SessionDep,
) -> BusinessEntityFieldValueRead | None:
    current = await _service(session).get_current_value(field_id)
    if current is None:
        return None
    return BusinessEntityFieldValueRead.model_validate(current)


@business_router.put(
    "/fields/{field_id}/current-value",
    response_model=BusinessEntityFieldValueRead,
    operation_id="setBusinessEntityFieldCurrentValue",
    summary="Replace the current accepted value of a field",
)
async def set_business_entity_field_current_value(
        field_id: int,
        payload: BusinessEntityFieldValueSet,
        session: SessionDep,
) -> BusinessEntityFieldValueRead:
    value = await _service(session).set_current_value(field_id, payload)
    return BusinessEntityFieldValueRead.model_validate(value)


@business_router.delete(
    "/fields/{field_id}/current-value",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="clearBusinessEntityFieldCurrentValue",
    summary="Close the current value without setting a replacement",
)
async def clear_business_entity_field_current_value(
        field_id: int,
        session: SessionDep,
) -> Response:
    await _service(session).clear_current_value(field_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@business_router.get(
    "/fields/{field_id}/history",
    response_model=list[BusinessEntityFieldValueRead],
    operation_id="getBusinessEntityFieldHistory",
    summary="Get value history of a field",
)
async def get_business_entity_field_history(
        field_id: int,
        session: SessionDep,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
) -> list[BusinessEntityFieldValueRead]:
    values = await _service(session).get_value_history(
        field_id,
        offset=offset,
        limit=limit,
    )
    return [BusinessEntityFieldValueRead.model_validate(value) for value in values]


@business_router.post(
    "/entities/{entity_id}/relations",
    response_model=BusinessEntityRelationRead,
    status_code=status.HTTP_201_CREATED,
    operation_id="createBusinessEntityRelation",
    summary="Create an outgoing relation from an entity",
)
async def create_business_entity_relation(
        entity_id: int,
        payload: BusinessEntityRelationCreate,
        session: SessionDep,
) -> BusinessEntityRelationRead:
    relation = await _service(session).create_relation(entity_id, payload)
    return BusinessEntityRelationRead.model_validate(relation)


@business_router.get(
    "/entities/{entity_id}/relations",
    response_model=list[BusinessEntityRelationRead],
    operation_id="listBusinessEntityRelations",
    summary="List relations of an entity",
)
async def list_business_entity_relations(
        entity_id: int,
        session: SessionDep,
        direction: Annotated[RelationDirection, Query()] = "both",
        relation_key: str | None = Query(default=None),
        active_only: bool = Query(default=True),
) -> list[BusinessEntityRelationRead]:
    relations = await _service(session).list_relations(
        entity_id,
        direction=direction,
        relation_key=relation_key,
        active_only=active_only,
    )
    return [
        BusinessEntityRelationRead.model_validate(relation) for relation in relations
    ]


@business_router.get(
    "/relations/{relation_id}",
    response_model=BusinessEntityRelationRead,
    operation_id="getBusinessEntityRelation",
    summary="Get a relation",
)
async def get_business_entity_relation(
        relation_id: int,
        session: SessionDep,
) -> BusinessEntityRelationRead:
    relation = await _service(session).get_relation(relation_id)
    return BusinessEntityRelationRead.model_validate(relation)


@business_router.delete(
    "/relations/{relation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="closeBusinessEntityRelation",
    summary="Close an active relation",
)
async def close_business_entity_relation(
        relation_id: int,
        session: SessionDep,
) -> Response:
    await _service(session).close_relation(relation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@business_router.get(
    "/entities/{entity_id}/revisions",
    response_model=list[BusinessEntityRevisionRead],
    operation_id="listBusinessEntityRevisions",
    summary="List logical revisions of an entity",
)
async def list_business_entity_revisions(
        entity_id: int,
        session: SessionDep,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
) -> list[BusinessEntityRevisionRead]:
    revisions = await _service(session).list_revisions(
        entity_id,
        offset=offset,
        limit=limit,
    )
    return [
        BusinessEntityRevisionRead.model_validate(revision) for revision in revisions
    ]


@business_router.get(
    "/revisions/{revision_id}",
    response_model=BusinessEntityRevisionRead,
    operation_id="getBusinessEntityRevision",
    summary="Get one logical entity revision",
)
async def get_business_entity_revision(
        revision_id: int,
        session: SessionDep,
) -> BusinessEntityRevisionRead:
    revision = await _service(session).get_revision(revision_id)
    return BusinessEntityRevisionRead.model_validate(revision)
