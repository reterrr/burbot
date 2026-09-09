from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from business_layer.schemas.enums import (
    BusinessEntityFieldCardinality,
    BusinessEntityFieldDataType,
    ConfirmedBy,
)

EntityType = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]
FieldKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=150),
]
FieldLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
RelationKey = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=150),
]


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ORMModel(APIModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class BusinessEntityCreate(APIModel):
    entity_type: EntityType


class BusinessEntityUpdate(APIModel):
    entity_type: EntityType | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("entity_type", ...) is None:
            raise ValueError("entity_type cannot be null")
        return data


class BusinessEntityRead(ORMModel):
    id: int
    entity_type: str
    created_at: datetime
    updated_at: datetime


class BusinessEntityFieldCreate(APIModel):
    key: FieldKey
    label: FieldLabel
    data_type: BusinessEntityFieldDataType
    cardinality: BusinessEntityFieldCardinality = BusinessEntityFieldCardinality.ONE
    required: bool = False
    description: str | None = None


class BusinessEntityFieldUpdate(APIModel):
    label: FieldLabel | None = None
    data_type: BusinessEntityFieldDataType | None = None
    cardinality: BusinessEntityFieldCardinality | None = None
    required: bool | None = None
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            null_fields = sorted(
                field
                for field in ("label", "data_type", "cardinality", "required")
                if data.get(field, ...) is None
            )
            if null_fields:
                raise ValueError(f"Fields cannot be null: {', '.join(null_fields)}")
        return data


class BusinessEntityFieldRead(ORMModel):
    id: int
    business_entity_id: int
    key: str
    label: str
    data_type: BusinessEntityFieldDataType
    cardinality: BusinessEntityFieldCardinality
    required: bool
    description: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


class BusinessEntityFieldValueSet(APIModel):
    value: JsonValue
    confirmed_by: ConfirmedBy = ConfirmedBy.SYSTEM
    reason: str | None = Field(default=None, max_length=255)
    revision_metadata: dict[str, JsonValue] | None = None


class BusinessEntityFieldValueRead(ORMModel):
    id: int
    business_entity_field_id: int
    revision_id: int | None
    value_json: Any
    confirmed_by: ConfirmedBy
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime


class BusinessEntityCurrentValueRead(APIModel):
    field_id: int
    key: str
    value: Any
    confirmed_by: ConfirmedBy
    valid_from: datetime
    revision_id: int | None = None


class BusinessEntityRelationCreate(APIModel):
    to_entity_id: int = Field(gt=0)
    relation_key: RelationKey
    metadata_json: dict[str, JsonValue] | None = None


class BusinessEntityRelationRead(ORMModel):
    id: int
    from_entity_id: int
    to_entity_id: int
    relation_key: str
    metadata_json: dict[str, Any] | None
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime


class BusinessEntityRevisionRead(ORMModel):
    id: int
    business_entity_id: int
    reason: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime


class BusinessEntityStateField(APIModel):
    field: BusinessEntityFieldRead
    current_value: BusinessEntityFieldValueRead | None


class BusinessEntityStateRead(APIModel):
    entity: BusinessEntityRead
    fields: list[BusinessEntityStateField]


class BusinessEntityStatePatch(APIModel):
    values: dict[str, JsonValue] = Field(min_length=1)
    confirmed_by: ConfirmedBy = ConfirmedBy.SYSTEM
    reason: str | None = Field(default=None, max_length=255)
    revision_metadata: dict[str, JsonValue] | None = None


RelationDirection = Literal["incoming", "outgoing", "both"]
