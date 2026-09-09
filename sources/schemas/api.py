"""Validated HTTP/service contracts for Layer 2."""

from datetime import datetime
from typing import Annotated, Any, Generic, Self, TypeVar

from pydantic import (
    AfterValidator,
    AnyHttpUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from sources.schemas.enums import (
    SourceState,
    SourceStateTrigger,
    SourceType,
    WarningSeverity,
    WarningStatus,
)


def canonical_url(value: AnyHttpUrl) -> AnyHttpUrl:
    if value.username is not None or value.password is not None:
        raise ValueError("Source URLs must not contain credentials")
    value = AnyHttpUrl(str(value).split("#", 1)[0])
    if len(str(value).encode("utf-8")) > 2048:
        raise ValueError("Source URLs must be at most 2048 bytes")
    return value


Identifier = Annotated[int, Field(gt=0, le=9223372036854775807)]
SourceURL = Annotated[AnyHttpUrl, AfterValidator(canonical_url)]
HashValue = Annotated[str, StringConstraints(min_length=1, max_length=64)]
SHA256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{64}$")]
NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Pagination(RequestModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=100)


T = TypeVar("T")


class Page(BaseModel, Generic[T]):  # noqa: UP046 - supports the declared Pydantic 2.9 minimum
    items: list[T]
    total: int
    offset: int
    limit: int


class PatchRequest(RequestModel):
    @model_validator(mode="after")
    def nonempty(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        for field in ("type", "tracking_enabled", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class StoredFileCreateRequest(RequestModel):
    storage_key: NonBlank
    original_name: NonBlank | None = None
    mime_type: NonBlank
    size_bytes: int | None = Field(default=None, ge=0, le=9223372036854775807)
    sha256: SHA256 | None = None


class StoredFileResponse(ResponseModel):
    id: int
    storage_key: str
    original_name: str | None
    mime_type: str
    size_bytes: int | None
    sha256: str | None
    created_at: datetime


class SourceCreateRequest(RequestModel):
    type: SourceType
    url: SourceURL | None = None
    file_id: Identifier | None = None

    @model_validator(mode="after")
    def locator_required(self) -> Self:
        if self.url is None and self.file_id is None:
            raise ValueError("A source requires url, file_id, or both")
        return self


class SourceUpdateRequest(PatchRequest):
    type: SourceType | None = None
    url: SourceURL | None = None
    file_id: Identifier | None = None


class SourceListRequest(Pagination):
    state: SourceState | None = None
    type: SourceType | None = None
    url: SourceURL | None = None


class SourceStateChangeRequest(RequestModel):
    state: SourceState
    expected_state: SourceState
    reason: str | None = Field(default=None, max_length=2000)
    triggered_by: SourceStateTrigger = SourceStateTrigger.USER


class SourceResponse(ResponseModel):
    id: int
    type: SourceType
    url: str | None
    file_id: int | None
    state: SourceState
    last_state_change_at: datetime
    created_at: datetime
    updated_at: datetime


class SourceStateHistoryResponse(ResponseModel):
    id: int
    source_id: int
    from_state: SourceState | None
    to_state: SourceState
    changed_at: datetime
    reason: str | None
    triggered_by: SourceStateTrigger


SourceListResponse = Page[SourceResponse]
SourceStateHistoryListResponse = Page[SourceStateHistoryResponse]


class SourceMetadataWrite(RequestModel):
    latest_content_hash: HashValue | None = None
    latest_structure_hash: HashValue | None = None
    hashes_updated_at: AwareDatetime | None = None


class SourceMetadataResponse(ResponseModel):
    source_id: int
    latest_content_hash: str | None
    latest_structure_hash: str | None
    hashes_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SourceCheckScheduleWrite(RequestModel):
    interval_seconds: int = Field(gt=0, le=2147483647)
    enabled: bool = True
    last_checked_at: AwareDatetime | None = None
    next_check_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def chronological(self) -> Self:
        if (
            self.last_checked_at
            and self.next_check_at
            and self.next_check_at < self.last_checked_at
        ):
            raise ValueError("next_check_at cannot be before last_checked_at")
        return self


class SourceCheckScheduleResponse(ResponseModel):
    source_id: int
    interval_seconds: int
    last_checked_at: datetime | None
    next_check_at: datetime | None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class SourceWarningCreate(RequestModel):
    severity: WarningSeverity = WarningSeverity.WARNING
    warning_type: NonBlank | None = None
    description: NonBlank
    details_json: dict[str, Any] | None = None


class SourceWarningUpdate(RequestModel):
    status: WarningStatus


class SourceWarningListRequest(Pagination):
    status: WarningStatus | None = None
    severity: WarningSeverity | None = None


class SourceWarningResponse(ResponseModel):
    id: int
    source_id: int
    severity: WarningSeverity
    status: WarningStatus
    warning_type: str | None
    description: str
    details_json: dict[str, Any] | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SourceBusinessEntityResponse(ResponseModel):
    source_id: int
    business_entity_id: int
    created_at: datetime


class SourceBusinessObjectResponse(ResponseModel):
    source_id: int
    business_object_id: int
    created_at: datetime


class SourceFieldTrackingCreate(RequestModel):
    business_entity_field_id: Identifier
    tracking_enabled: bool = True
    desired_refresh_seconds: int | None = Field(default=None, gt=0, le=2147483647)


class SourceFieldTrackingUpdate(PatchRequest):
    tracking_enabled: bool | None = None
    desired_refresh_seconds: int | None = Field(default=None, gt=0, le=2147483647)


class SourceFieldTrackingResponse(ResponseModel):
    id: int
    source_id: int
    business_entity_field_id: int
    tracking_enabled: bool
    desired_refresh_seconds: int | None
    created_at: datetime
    updated_at: datetime


class SourceObjectFieldTrackingCreate(RequestModel):
    business_object_field_id: Identifier
    tracking_enabled: bool = True


class SourceObjectFieldTrackingUpdate(PatchRequest):
    tracking_enabled: bool | None = None
    last_observation_id: Identifier | None = None
    baseline_observation_id: Identifier | None = None
    last_checked_at: AwareDatetime | None = None
    last_changed_at: AwareDatetime | None = None


class SourceObjectFieldTrackingResponse(ResponseModel):
    id: int
    source_field_tracking_id: int
    business_object_field_id: int
    tracking_enabled: bool
    last_observation_id: int | None
    baseline_observation_id: int | None
    last_checked_at: datetime | None
    last_changed_at: datetime | None
    created_at: datetime
    updated_at: datetime
