from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlmodel import SQLModel

from business_layer.schemas.enums import (
    BusinessDefinitionStatus,
    BusinessRelationCardinality,
)


# ============================================================
# BusinessModel
# ============================================================

class BusinessModelFilter(SQLModel):
    id: int | None = None
    key: str | None = None
    name: str | None = None
    description: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime | None = None


class BusinessModelAdd(SQLModel):
    key: str
    name: str
    description: str | None = None
    metadata_json: dict[str, Any] | None = None


class BusinessModelUpdate(SQLModel):
    key: str | None = None
    name: str | None = None
    description: str | None = None
    metadata_json: dict[str, Any] | None = None


# ============================================================
# BusinessModelRevision
# ============================================================

class BusinessModelRevisionFilter(SQLModel):
    id: int | None = None
    business_model_id: int | None = None
    reason: str | None = None
    metadata_json: dict[str, Any] | None = None
    created_at: datetime | None = None


class BusinessModelRevisionAdd(SQLModel):
    business_model_id: int
    reason: str | None = None
    metadata_json: dict[str, Any] | None = None


class BusinessModelRevisionUpdate(SQLModel):
    reason: str | None = None
    metadata_json: dict[str, Any] | None = None


# ============================================================
# BusinessEntity
# ============================================================

class BusinessEntityFilter(SQLModel):
    id: int | None = None
    business_model_id: int | None = None
    physical_name: str | None = None
    tablename: str | None = None
    created_at: datetime | None = None


class BusinessEntityAdd(SQLModel):
    business_model_id: int
    table_name: str
    physical_name: str | None = None


class BusinessEntityUpdate(SQLModel):
    business_model_id: int | None = None
    table_name: str | None = None
    physical_name: str | None = None


# ============================================================
# BusinessEntityVersion
# ============================================================

class BusinessEntityVersionFilter(SQLModel):
    id: int | None = None
    business_entity_id: int | None = None
    revision_id: int | None = None

    key: str | None = None
    label: str | None = None
    description: str | None = None
    status: BusinessDefinitionStatus | None = None

    definition_json: dict[str, Any] | None = None

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    transaction_from: datetime | None = None
    transaction_to: datetime | None = None

    created_at: datetime | None = None


class BusinessEntityVersionAdd(SQLModel):
    business_entity_id: int
    revision_id: int

    key: str
    label: str

    description: str | None = None

    status: BusinessDefinitionStatus = BusinessDefinitionStatus.ACTIVE

    definition_json: dict[str, Any] | None = None

    valid_from: datetime
    valid_to: datetime | None = None


class BusinessEntityVersionUpdate(SQLModel):
    revision_id: int | None = None

    key: str | None = None
    label: str | None = None
    description: str | None = None
    status: BusinessDefinitionStatus | None = None

    definition_json: dict[str, Any] | None = None

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    transaction_to: datetime | None = None


# ============================================================
# BusinessEntityField
# ============================================================

class BusinessEntityFieldFilter(SQLModel):
    id: int | None = None
    business_entity_id: int | None = None
    physical_name: str | None = None
    created_at: datetime | None = None


class BusinessEntityFieldAdd(SQLModel):
    business_entity_id: int
    physical_name: str | None = None


class BusinessEntityFieldUpdate(SQLModel):
    business_entity_id: int | None = None
    physical_name: str | None = None


# ============================================================
# BusinessEntityFieldVersion
# ============================================================

class BusinessEntityFieldVersionFilter(SQLModel):
    id: int | None = None

    business_entity_field_id: int | None = None
    revision_id: int | None = None

    key: str | None = None
    label: str | None = None
    description: str | None = None
    status: BusinessDefinitionStatus | None = None

    definition_json: dict[str, Any] | None = None

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    transaction_from: datetime | None = None
    transaction_to: datetime | None = None

    created_at: datetime | None = None


class BusinessEntityFieldVersionAdd(SQLModel):
    business_entity_field_id: int
    revision_id: int

    key: str
    label: str

    description: str | None = None

    status: BusinessDefinitionStatus = BusinessDefinitionStatus.ACTIVE

    definition_json: dict[str, Any]

    valid_from: datetime
    valid_to: datetime | None = None


class BusinessEntityFieldVersionUpdate(SQLModel):
    revision_id: int | None = None

    key: str | None = None
    label: str | None = None
    description: str | None = None
    status: BusinessDefinitionStatus | None = None

    definition_json: dict[str, Any] | None = None

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    transaction_to: datetime | None = None


# ============================================================
# BusinessEntityRelation
# ============================================================

class BusinessEntityRelationFilter(SQLModel):
    id: int | None = None
    business_model_id: int | None = None
    created_at: datetime | None = None


class BusinessEntityRelationAdd(SQLModel):
    business_model_id: int


class BusinessEntityRelationUpdate(SQLModel):
    business_model_id: int | None = None


# ============================================================
# BusinessEntityRelationVersion
# ============================================================

class BusinessEntityRelationVersionFilter(SQLModel):
    id: int | None = None

    business_entity_relation_id: int | None = None
    revision_id: int | None = None

    key: str | None = None
    label: str | None = None
    description: str | None = None

    from_entity_id: int | None = None
    to_entity_id: int | None = None

    from_field_id: int | None = None
    to_field_id: int | None = None

    cardinality: BusinessRelationCardinality | None = None
    status: BusinessDefinitionStatus | None = None

    definition_json: dict[str, Any] | None = None

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    transaction_from: datetime | None = None
    transaction_to: datetime | None = None

    created_at: datetime | None = None


class BusinessEntityRelationVersionAdd(SQLModel):
    business_entity_relation_id: int
    revision_id: int

    key: str

    label: str | None = None
    description: str | None = None

    from_entity_id: int
    to_entity_id: int

    from_field_id: int | None = None
    to_field_id: int | None = None

    cardinality: BusinessRelationCardinality

    status: BusinessDefinitionStatus = BusinessDefinitionStatus.ACTIVE

    definition_json: dict[str, Any] | None = None

    valid_from: datetime
    valid_to: datetime | None = None


class BusinessEntityRelationVersionUpdate(SQLModel):
    revision_id: int | None = None

    key: str | None = None
    label: str | None = None
    description: str | None = None

    from_entity_id: int | None = None
    to_entity_id: int | None = None

    from_field_id: int | None = None
    to_field_id: int | None = None

    cardinality: BusinessRelationCardinality | None = None
    status: BusinessDefinitionStatus | None = None

    definition_json: dict[str, Any] | None = None

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    transaction_to: datetime | None = None


# ============================================================
# BusinessObject
# ============================================================

class BusinessObjectFilter(SQLModel):
    id: int | None = None
    business_entity_id: int | None = None
    created_at: datetime | None = None


class BusinessObjectAdd(SQLModel):
    business_entity_id: int


class BusinessObjectUpdate(SQLModel):
    business_entity_id: int | None = None


# ============================================================
# BusinessObjectField
# ============================================================

class BusinessObjectFieldFilter(SQLModel):
    id: int | None = None

    business_object_id: int | None = None
    business_entity_field_id: int | None = None

    created_at: datetime | None = None


class BusinessObjectFieldAdd(SQLModel):
    business_object_id: int
    business_entity_field_id: int


class BusinessObjectFieldUpdate(SQLModel):
    business_object_id: int | None = None
    business_entity_field_id: int | None = None


# ============================================================
# BusinessObjectFieldValue
# ============================================================

class BusinessObjectFieldValueFilter(SQLModel):
    id: int | None = None

    business_object_field_id: int | None = None

    value_json: Any | None = None

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    transaction_from: datetime | None = None
    transaction_to: datetime | None = None

    created_at: datetime | None = None


class BusinessObjectFieldValueAdd(SQLModel):
    business_object_field_id: int

    value_json: Any

    valid_from: datetime
    valid_to: datetime | None = None


class BusinessObjectFieldValueUpdate(SQLModel):
    value_json: Any | None = None

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    transaction_to: datetime | None = None


class CreateObjectResponse(BaseModel):
    object_id: int

    # business_entity_field_id -> business_object_field_id
    object_fields: dict[int, int]


class AssignFieldValuesRequest(BaseModel):
    # business_object_field_id -> JSON value
    field_values: dict[int, Any] = Field(min_length=1)


class BusinessObjectFieldRead(BaseModel):
    object_field_id: int
    business_entity_field_id: int

    value_id: int | None = None
    value: Any | None = None

    valid_from: datetime | None = None


class BusinessObjectRead(BaseModel):
    id: int
    business_entity_id: int
    created_at: datetime

    fields: list[BusinessObjectFieldRead]


class BusinessObjectFieldValueRead(BaseModel):
    id: int
    business_object_field_id: int
    value: Any

    valid_from: datetime
    valid_to: datetime | None

    transaction_from: datetime
    transaction_to: datetime | None

    created_at: datetime
