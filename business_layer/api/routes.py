from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status, Query,
)
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from business_layer.api.dependencies import BusinessServiceDep
from business_layer.schemas.models import (
    BusinessModel,
    BusinessModelRevision,
)
from business_layer.schemas.models.dtos import BusinessObjectRead, AssignFieldValuesRequest, \
    BusinessObjectFieldValueRead, CreateObjectResponse
from business_layer.services.business import (
    RegisterResult,
    SchemaChange,
)
from business_layer.services.schema_language import Sema

router = APIRouter(
    prefix="/business",
    tags=["business"],
)

# ============================================================
# Constants
# ============================================================

SCHEMA_METADATA_KEY = "schema"
SCHEMA_HASH_METADATA_KEY = "schema_hash"
SCHEMA_HASH_VERSION_METADATA_KEY = "schema_hash_version"

RESERVED_REVISION_METADATA_KEYS = {
    SCHEMA_METADATA_KEY,
    SCHEMA_HASH_METADATA_KEY,
    SCHEMA_HASH_VERSION_METADATA_KEY,
}


# ============================================================
# Common contracts
# ============================================================

class PaginationRequest(BaseModel):
    offset: int = Field(
        default=0,
        ge=0,
    )

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )


# ============================================================
# BusinessModel contracts
# ============================================================

class BusinessModelCreateRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    key: str
    name: str

    description: str | None = None
    metadata_json: dict[str, Any] | None = None


class BusinessModelListResponse(BaseModel):
    items: list[BusinessModel]

    offset: int
    limit: int
    total: int


# ============================================================
# Revision contracts
# ============================================================

class BusinessModelRevisionSummary(BaseModel):
    """
    Lightweight revision representation.

    Deliberately does NOT include the entire schema because
    revision lists could otherwise become extremely large.
    """

    id: int
    business_model_id: int

    reason: str | None = None

    schema_hash: str | None = None

    created_at: datetime


class BusinessModelRevisionListResponse(BaseModel):
    items: list[BusinessModelRevisionSummary]

    offset: int
    limit: int
    total: int


class BusinessModelRevisionResponse(BaseModel):
    """
    Complete single revision.

    Internal metadata storage:

        metadata_json = {
            "schema": {...},
            "schema_hash": "...",
            "schema_hash_version": 1,
            ...user metadata...
        }

    API response separates those concerns.
    """

    id: int
    business_model_id: int

    reason: str | None = None

    schema: Sema.Schema

    schema_hash: str | None = None
    schema_hash_version: int | None = None

    # Only user-provided metadata.
    metadata_json: dict[str, Any]

    created_at: datetime


# ============================================================
# Schema registration contracts
# ============================================================

class SchemaRegisterRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    schema: Sema.Schema

    reason: str | None = None

    # User metadata only.
    #
    # schema/schema_hash/etc. are controlled by Burbot.
    metadata_json: dict[str, Any] | None = None


class SchemaChangeResponse(BaseModel):
    action: str
    resource: str

    entity: str
    field: str | None = None


class SchemaRegisterResponse(BaseModel):
    changed: bool

    revision_id: int | None

    changes: list[SchemaChangeResponse]

    message: str


# ============================================================
# Response helpers
# ============================================================

def change_response(
        change: SchemaChange,
) -> SchemaChangeResponse:
    return SchemaChangeResponse(
        action=change.action,
        resource=change.resource,
        entity=change.entity,
        field=change.field,
    )


def register_response(
        result: RegisterResult,
) -> SchemaRegisterResponse:
    return SchemaRegisterResponse(
        changed=result.changed,
        revision_id=result.revision_id,

        changes=[
            change_response(change)
            for change in result.changes
        ],

        message=result.message,
    )


def revision_summary_response(
        revision: BusinessModelRevision,
) -> BusinessModelRevisionSummary:
    revision_id = revision.id

    if revision_id is None:
        raise RuntimeError(
            "BusinessModelRevision has no id"
        )

    metadata = revision.metadata_json or {}

    schema_hash = metadata.get(
        SCHEMA_HASH_METADATA_KEY
    )

    if not isinstance(schema_hash, str):
        schema_hash = None

    return BusinessModelRevisionSummary(
        id=revision_id,
        business_model_id=revision.business_model_id,
        reason=revision.reason,
        schema_hash=schema_hash,
        created_at=revision.created_at,
    )


def revision_response(
        revision: BusinessModelRevision,
) -> BusinessModelRevisionResponse:
    revision_id = revision.id

    if revision_id is None:
        raise RuntimeError(
            "BusinessModelRevision has no id"
        )

    metadata = dict(
        revision.metadata_json or {}
    )

    raw_schema = metadata.pop(
        SCHEMA_METADATA_KEY,
        None,
    )

    if raw_schema is None:
        raise RuntimeError(
            f"Revision {revision_id} "
            f"does not contain schema metadata"
        )

    # New format:
    #
    # "schema": { ... }
    if isinstance(raw_schema, dict):
        schema = Sema.Schema.model_validate(
            raw_schema
        )

    # Backwards compatibility with revisions created when
    # schema was stored using model_dump_json().
    elif isinstance(raw_schema, str):
        schema = Sema.Schema.model_validate_json(
            raw_schema
        )

    else:
        raise RuntimeError(
            f"Revision {revision_id} contains "
            f"invalid schema metadata"
        )

    schema_hash = metadata.pop(
        SCHEMA_HASH_METADATA_KEY,
        None,
    )

    schema_hash_version = metadata.pop(
        SCHEMA_HASH_VERSION_METADATA_KEY,
        None,
    )

    return BusinessModelRevisionResponse(
        id=revision_id,
        business_model_id=revision.business_model_id,

        reason=revision.reason,

        schema=schema,

        schema_hash=(
            schema_hash
            if isinstance(schema_hash, str)
            else None
        ),

        schema_hash_version=(
            schema_hash_version
            if isinstance(schema_hash_version, int)
            else None
        ),

        # Internal revision metadata has been removed.
        metadata_json=metadata,

        created_at=revision.created_at,
    )


# ============================================================
# Error helpers
# ============================================================

def sema_http_exception(
        exception: Sema.SemaException,
) -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_422_UNPROCESSABLE_ENTITY
        ),
        detail={
            "message": exception.description,

            "location": {
                "line": exception.location.line,
                "column": exception.location.column,
            },
        },
    )


# ============================================================
# Business Models
# ============================================================

# ------------------------------------------------------------
# CREATE model
# ------------------------------------------------------------

@router.post(
    "/models",
    response_model=BusinessModel,
    status_code=status.HTTP_201_CREATED,
)
async def create_business_model(
        request: BusinessModelCreateRequest,
        service: BusinessServiceDep,
) -> BusinessModel:
    try:
        return await service.create_model(
            key=request.key,
            name=request.name,
            description=request.description,
            metadata_json=request.metadata_json,
        )

    except IntegrityError as exception:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Business model with this key "
                "already exists"
            ),
        ) from exception


# ------------------------------------------------------------
# LIST models
#
# GET /business/models?offset=0&limit=20
# ------------------------------------------------------------

@router.get(
    "/models",
    response_model=BusinessModelListResponse,
)
async def get_models(
        service: BusinessServiceDep,
        request: PaginationRequest = Depends(),
) -> BusinessModelListResponse:
    models, total = await service.get_models(
        offset=request.offset,
        limit=request.limit,
    )

    return BusinessModelListResponse(
        items=models,
        offset=request.offset,
        limit=request.limit,
        total=total,
    )


# ------------------------------------------------------------
# GET one model
#
# Important:
# BusinessModel itself contains current_revision_id.
# ------------------------------------------------------------

@router.get(
    "/models/{model_id}",
    response_model=BusinessModel,
)
async def get_model(
        model_id: int,
        service: BusinessServiceDep,
) -> BusinessModel:
    try:
        return await service.get_model(
            model_id
        )

    except LookupError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception


@router.get(
    "/models/{model_id}/revisions/count",
    response_model=int,
)
async def get_revision_count(
        model_id: int,
        service: BusinessServiceDep
) -> int:
    return await service.get_revisions_count(model_id)


# ============================================================
# Revisions
# ============================================================

# ------------------------------------------------------------
# LIST revisions
#
# GET
# /business/models/1/revisions?offset=0&limit=20
#
# Returns summaries only.
# Does not send each complete Sema.Schema.
# ------------------------------------------------------------

@router.get(
    "/models/{model_id}/revisions",
    response_model=BusinessModelRevisionListResponse,
)
async def get_model_revisions(
        model_id: int,
        service: BusinessServiceDep,
        request: PaginationRequest = Depends(),
) -> BusinessModelRevisionListResponse:
    try:
        revisions, total = await service.get_revisions(
            model_id=model_id,
            offset=request.offset,
            limit=request.limit,
        )

        return BusinessModelRevisionListResponse(
            items=[
                revision_summary_response(revision)
                for revision in revisions
            ],

            offset=request.offset,
            limit=request.limit,
            total=total,
        )

    except LookupError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception


# ------------------------------------------------------------
# GET one revision
#
# This contains the complete semantic schema.
#
# GET /business/models/1/revisions/15
# ------------------------------------------------------------

@router.get(
    "/models/{model_id}/revisions/{revision_id}",
    response_model=BusinessModelRevisionResponse,
)
async def get_model_revision(
        model_id: int,
        revision_id: int,
        service: BusinessServiceDep,
) -> BusinessModelRevisionResponse:
    try:
        revision = await service.get_revision(
            model_id=model_id,
            revision_id=revision_id,
        )

        return revision_response(
            revision
        )

    except LookupError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception


# ------------------------------------------------------------
# CREATE / REGISTER revision
#
# POST /business/models/1/revisions
# ------------------------------------------------------------

@router.post(
    "/models/{model_id}/revisions",
    response_model=SchemaRegisterResponse,
    status_code=status.HTTP_200_OK,
)
async def register_business_schema(
        model_id: int,
        request: SchemaRegisterRequest,
        service: BusinessServiceDep,
) -> SchemaRegisterResponse:
    try:
        metadata_json = dict(
            request.metadata_json or {}
        )

        # --------------------------------------------
        # These belong to Burbot itself.
        # User must not overwrite them.
        # --------------------------------------------

        provided_reserved = (
                RESERVED_REVISION_METADATA_KEYS
                & metadata_json.keys()
        )

        if provided_reserved:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail={
                    "message": (
                        "Reserved revision metadata provided"
                    ),

                    "keys": sorted(
                        provided_reserved
                    ),
                },
            )

        result = await service.register(
            model_id=model_id,
            reason=request.reason,
            metadata_json=metadata_json,
            scheme=request.schema,
        )

        return register_response(
            result
        )

    except Sema.SemaException as exception:
        raise sema_http_exception(
            exception
        ) from exception

    except LookupError as exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exception),
        ) from exception


@router.post(
    "/entities/{entity_id}/objects",
    response_model=CreateObjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_object(
    entity_id: int,
    service: BusinessServiceDep,
) -> CreateObjectResponse:
    return await service.create_object(entity_id)


@router.get(
    "/entities/{entity_id}/objects",
    response_model=list[BusinessObjectRead],
)
async def list_objects(
    entity_id: int,
    service: BusinessServiceDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[BusinessObjectRead]:
    return await service.list_objects(
        entity_id,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/objects/{object_id}",
    response_model=BusinessObjectRead,
)
async def get_object(
    object_id: int,
    service: BusinessServiceDep,
) -> BusinessObjectRead:
    return await service.get_object(object_id)


@router.patch(
    "/objects/{object_id}/values",
    response_model=BusinessObjectRead,
)
async def assign_object_field_values(
    object_id: int,
    payload: AssignFieldValuesRequest,
    service: BusinessServiceDep,
) -> BusinessObjectRead:
    return await service.assign_object_fields_values(
        object_id,
        payload.field_values,
    )


@router.delete(
    "/objects/{object_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_object(
    object_id: int,
    service: BusinessServiceDep,
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
    service: BusinessServiceDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[BusinessObjectFieldValueRead]:
    return await service.get_object_field_value_history(
        object_field_id,
        offset=offset,
        limit=limit,
    )
