from __future__ import annotations

from datetime import datetime
from typing import Annotated, Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from extraction.schemas.models import ExtractionRunStatus

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


class CreateExtractionConcreteValueRequest(RequestModel):
    concrete_value: NonBlank
    char_start: int = Field(ge=0, le=2147483647)
    char_end: int = Field(gt=0, le=2147483647)
    token_class_id: TokenClassId
    object_field_id: Identifier

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        return self


class SetExtractionFieldEvidenceRequest(RequestModel):
    snapshot_id: Identifier
    values: list[CreateExtractionConcreteValueRequest] = Field(min_length=1)


class CreateFieldObservationRequest(RequestModel):
    object_id: Identifier
    concrete_values: list[SetExtractionFieldEvidenceRequest] = Field(min_length=1)


class CreateExtractionRunRequest(RequestModel):
    workflow_id: Identifier
    field_observations: list[CreateFieldObservationRequest] = Field(min_length=1)


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
