from __future__ import annotations

from datetime import datetime
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from extraction.schemas.enums import ExtractionRunStatus

Identifier = Annotated[int, Field(gt=0, le=9223372036854775807)]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
TokenClassId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)
]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Pagination(RequestModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=100)


class ExtractionRunListRequest(Pagination):
    workflow_id: Identifier | None = None
    source_id: Identifier | None = None


T = TypeVar("T")


class Page(BaseModel, Generic[T]):  # noqa: UP046 - supports Pydantic 2.9
    items: list[T]
    total: int
    offset: int
    limit: int


class ConcreteValueResponse(ResponseModel):
    id: int
    snapshot_id: int
    concrete_value: str
    char_start: int | None
    char_end: int | None
    token_class_id: str
    value_index: int


class FieldObservationResponse(ResponseModel):
    id: int
    business_object_id: int | None
    business_object_field_id: int | None
    tracking_version_id: int | None
    observed_at: datetime
    concrete_values: list[ConcreteValueResponse]


class ExtractionRunSummary(ResponseModel):
    id: int
    workflow_id: int | None
    source_id: int
    source_snapshot_id: int
    status: ExtractionRunStatus
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime


class ExtractionRunResponse(ExtractionRunSummary):
    field_observations: list[FieldObservationResponse]


ExtractionRunListResponse = Page[ExtractionRunSummary]
