"""Validated request and response contracts for the source registry."""

from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    model_validator,
)

from sources.schemas.enums import SourceState, SourceStateTrigger, SourceType


def canonical_url(value: AnyHttpUrl) -> AnyHttpUrl:
    if value.username is not None or value.password is not None:
        raise ValueError("Source URLs must not contain credentials")
    value = AnyHttpUrl(str(value).split("#", 1)[0])
    if len(str(value).encode("utf-8")) > 2048:
        raise ValueError("Source URLs must be at most 2048 bytes")
    return value


SourceURL = Annotated[AnyHttpUrl, AfterValidator(canonical_url)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceCreateRequest(RequestModel):
    url: SourceURL
    source_type: SourceType
    file_id: PositiveInt | None = None


class SourceUpdateRequest(RequestModel):
    """Correct registration details before discovery has started."""

    url: SourceURL | None = None
    source_type: SourceType | None = None
    file_id: PositiveInt | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field in ("url", "source_type"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class Pagination(RequestModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=100)


class SourceListRequest(Pagination):
    state: SourceState | None = None
    source_type: SourceType | None = None
    url: SourceURL | None = None


class SourceStateChangeRequest(RequestModel):
    state: SourceState
    expected_state: SourceState
    reason: str | None = Field(default=None, max_length=2000)
    triggered_by: SourceStateTrigger = SourceStateTrigger.USER


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    source_type: SourceType
    file_id: int | None
    state: SourceState
    last_state_change_at: datetime
    created_at: datetime
    updated_at: datetime


class SourceListResponse(BaseModel):
    items: list[SourceResponse]
    total: int
    offset: int
    limit: int


class SourceStateHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    from_state: SourceState | None
    to_state: SourceState
    changed_at: datetime
    reason: str | None
    triggered_by: SourceStateTrigger


class SourceStateHistoryListResponse(BaseModel):
    items: list[SourceStateHistoryResponse]
    total: int
    offset: int
    limit: int
