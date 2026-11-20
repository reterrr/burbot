from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, Field

from business_layer.schemas.enums import (
    BusinessDefinitionStatus,
)


class CreateObjectResponse(BaseModel):
    object_id: int

    # business_entity_field_id -> business_object_field_id
    object_fields: dict[int, int]


class AssignFieldValuesRequest(BaseModel):
    # business_object_field_id -> JSON value
    field_values: dict[int, Any] = Field(min_length=1)
    effective_at: datetime | None = None
    expected_value_ids: dict[int, int | None] | None = None
    expected_collection_revisions: dict[int, Annotated[int, Field(strict=True, ge=0)]] | None = None


class BusinessObjectFieldRead(BaseModel):
    object_field_id: int
    business_entity_field_id: int

    value_id: int | None = None
    validated_against_field_version_id: int | None = None
    collection_id: int | None = None
    collection_revision: int | None = None
    value: Any | None = None

    valid_from: datetime | None = None


class CreateObjectRequest(BaseModel):
    values: dict[int, Any] = Field(default_factory=dict)


class BusinessObjectRead(BaseModel):
    archived_at: datetime | None = None
    id: int
    business_entity_id: int
    created_at: datetime

    fields: list[BusinessObjectFieldRead]


class BusinessObjectFieldValueRead(BaseModel):
    id: int
    business_object_field_id: int
    validated_against_field_version_id: int
    value: Any
    collection_id: int | None = None

    valid_from: datetime
    valid_to: datetime | None

    transaction_from: datetime
    transaction_to: datetime | None

    created_at: datetime


class FieldDefinitionRead(BaseModel):
    persistent_key: str
    field_id: int
    entity_id: int
    version_id: int
    key: str
    label: str
    description: str | None = None
    status: BusinessDefinitionStatus
    definition: dict[str, Any]


class EntityDefinitionRead(BaseModel):
    entity_id: int
    model_id: int
    table_name: str
    version_id: int
    key: str
    label: str
    status: BusinessDefinitionStatus
    fields: list[FieldDefinitionRead]
