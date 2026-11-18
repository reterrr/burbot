"""Public collection contracts; revision guards every addressed mutation."""

from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

Revision = Annotated[int, Field(strict=True, ge=0)]
Identity = Annotated[int, Field(strict=True, gt=0)]
Position = Annotated[int, Field(strict=True, ge=0)]


class CollectionItemRead(BaseModel):
    id: int
    version_id: int
    position: int
    value: JsonValue
    valid_from: datetime


class CollectionRead(BaseModel):
    id: int
    root_field_id: int | None
    parent_item_id: int | None
    revision: int
    created_at: datetime
    active: bool
    items: list[CollectionItemRead]


class CollectionItemsRead(BaseModel):
    items: list[CollectionItemRead]
    total: int
    offset: int
    limit: int
    revision: int


class CollectionItemHistory(BaseModel):
    id: int
    item_id: int
    position: int | None
    present: bool
    value: JsonValue
    valid_from: datetime
    valid_to: datetime | None
    transaction_from: datetime
    transaction_to: datetime | None


class CollectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: list[JsonValue] = Field(default_factory=list)
    expected_value_id: Identity | None = None
    effective_at: AwareDatetime | None = None


class CollectionMutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: Revision
    effective_at: AwareDatetime | None = None


class CollectionInsert(CollectionMutation):
    value: JsonValue
    position: Position | None = None


class CollectionPatch(CollectionMutation):
    value: JsonValue = None
    position: Position | None = None

    @model_validator(mode="after")
    def one_operation(self):
        supplied = self.model_fields_set & {"value", "position"}
        if len(supplied) != 1 or supplied == {"position"} and self.position is None:
            raise ValueError("Supply exactly one of value or position")
        return self


class CollectionReorder(CollectionMutation):
    item_ids: list[Identity]


class CollectionReplace(CollectionMutation):
    values: list[JsonValue]
