"""Browser Agent and operator workspace wire contracts."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, model_validator

from business_layer.schemas.models.dtos import BusinessFieldDisplay, BusinessValueDisplay
from extraction.schemas.api import Identifier
from extraction.schemas.selector_tree import (
    PortableModel,
    SelectorEvaluationResult,
    SelectorVersionDefinition,
)
from monitoring.onboarding_config import PolicyName
from sources.schemas.api import SourceSnapshotResponse

REPRESENTATION = "rendered_dom"
REPRESENTATION_VERSION = "firefox-dom-1"
STRUCTURE_HASH_VERSION = "dom-shape-1"
MIME_TYPE = "text/html"
MAX_BYTES = 5 * 1024 * 1024
MAX_SELECTORS = 64

Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
URL = Annotated[str, StringConstraints(min_length=1, max_length=2048)]


class ReviewedSource(BaseModel):
    id: int
    url: str | None
    name: str | None = None


class SnapshotArtifactDetails(BaseModel):
    mimeType: str
    sizeBytes: int | None
    sha256: str | None


class SnapshotDetails(BaseModel):
    source: ReviewedSource
    snapshot: SourceSnapshotResponse
    artifact: SnapshotArtifactDetails | None


class SnapshotContent(SnapshotDetails):
    html: str | None = None


SnapshotCommandState = Literal["pending", "claimed", "opened", "failed", "expired"]
SnapshotCommandError = Literal[
    "SNAPSHOT_ARTIFACT_NOT_FOUND",
    "SNAPSHOT_INTEGRITY_MISMATCH",
    "SNAPSHOT_TOO_LARGE",
    "SNAPSHOT_NOT_HTML",
    "SNAPSHOT_DIGEST_UNAVAILABLE",
    "SNAPSHOT_SOURCE_FORBIDDEN",
    "SNAPSHOT_UNAVAILABLE",
    "BACKEND_TIMEOUT",
    "INVALID_ARTIFACT",
    "VIEWER_OPEN_FAILED",
    "VIEWER_INTERRUPTED",
]


class SnapshotSelectorContext(PortableModel):
    extraction_run_id: Identifier
    selector_uuid: UUID
    selector_version_uuid: UUID


class OpenSnapshotRequest(PortableModel):
    request_id: UUID
    source_id: Identifier
    snapshot_id: Identifier
    target_agent_id: UUID | None = None
    action: Literal["open_snapshot"] = "open_snapshot"
    selector_context: SnapshotSelectorContext | None = None


class SnapshotAgentChoice(PortableModel):
    agent_id: UUID
    name: str


class SnapshotCommandResponse(PortableModel):
    command_id: UUID
    source_id: int
    snapshot_id: int
    target_agent_id: UUID
    action: Literal["open_snapshot"] = "open_snapshot"
    created_at: datetime
    expires_at: datetime
    state: SnapshotCommandState
    error_code: SnapshotCommandError | None = None


class ClaimedSnapshotCommand(SnapshotCommandResponse):
    source_url: str | None
    captured_at: datetime
    selector_context: SnapshotSelectorContext | None = None
    selector: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None


class SnapshotCommandAck(PortableModel):
    state: Literal["opened", "failed"]
    error_code: SnapshotCommandError | None = None

    @model_validator(mode="after")
    def validate_result(self):
        if (self.state == "failed") != (self.error_code is not None):
            raise ValueError("A failed result requires an error code")
        return self


class ReviewedObject(BaseModel):
    id: int
    name: str | None


class TaskReferenceDisplay(BaseModel):
    label: str | None = None
    capturedAt: datetime | None = None
    status: str | None = None


class ReviewedFieldValues(BaseModel):
    businessField: BusinessFieldDisplay | None = None
    businessObjectFieldId: int | None
    businessObject: ReviewedObject | None = None
    canonicalValueId: int | None
    canonicalValue: Any
    canonicalDisplay: BusinessValueDisplay | None = None
    previousObservationId: int | None
    observationId: int | None
    previousEvidence: str | list[str] | None
    currentEvidence: str | list[str] | None
    evaluationId: int | None


class EvidenceReviewResponse(ReviewedFieldValues):
    taskId: int
    taskStatus: str
    source: ReviewedSource
    snapshot: SourceSnapshotResponse | None
    extractionRunId: int | None
    selector: dict[str, Any] | None
    evaluation: dict[str, Any] | None
    baselineObservationId: int | None
    comparison: str | None
    evidenceStatus: str | None
    evidenceChanged: bool | None
    requiresReview: bool
    referenceDisplays: dict[int, TaskReferenceDisplay] | None = None


class TrackedFieldResponse(ReviewedFieldValues):
    selectorUuid: UUID
    selectorVersionId: int | None
    selectorVersionUuid: UUID | None
    configured: bool
    status: str | None
    task: dict[str, Any] | None


class SourceReviewResponse(BaseModel):
    id: int
    source: dict[str, Any]
    latestCheck: dict[str, Any] | None
    latestCompletedCheck: dict[str, Any] | None
    selectedCheck: dict[str, Any] | None
    snapshot: SourceSnapshotResponse | None
    fields: list[TrackedFieldResponse]
    earlierTasks: dict[str, Any]


class ObjectReviewName(ReviewedObject):
    code: str | None
    entityId: int
    entityName: str | None


class MonitoringPage[T](BaseModel):
    total: int
    offset: int
    limit: int
    items: list[T]


class ObjectInboxItem(BaseModel):
    object: ObjectReviewName
    sourceCount: int
    taskCount: int
    fieldCount: int
    lastCheckedAt: datetime | None
    status: Literal["pending", "in_progress"]
    severity: Literal["high", "normal", "informational"]


class ObjectFinding(BaseModel):
    businessField: BusinessFieldDisplay
    businessObjectFieldId: int
    selectorUuid: UUID
    selectorVersionUuid: UUID | None
    status: str
    checkId: UUID
    checkedAt: datetime | None
    snapshotId: int | None
    observationId: int | None
    evaluationId: int | None


class ObjectReviewTask(BaseModel):
    id: int
    type: str
    title: str | None
    status: str
    workflowStatus: str
    originCheckId: UUID
    snapshotId: int | None
    checkedAt: datetime | None
    requiresReview: bool
    source: ReviewedSource
    allowedStatuses: list[str]
    fields: list[ObjectFinding]


class ObjectReviewResponse(BaseModel):
    object: ObjectReviewName
    tasks: MonitoringPage[ObjectReviewTask]


class FindingCapture(BaseModel):
    checkId: UUID
    checkedAt: datetime | None
    snapshotId: int | None
    fields: list[ObjectFinding]


class Approval(PortableModel):
    enabled: bool = True
    additional_origins: list[URL] = Field(default_factory=list, max_length=20)


class RegisterAgent(PortableModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    source_ids: list[Identifier] = Field(default_factory=list, max_length=250)
    trusted: bool = False


class AgentSourcesUpdate(PortableModel):
    add_source_ids: list[Identifier] = Field(default_factory=list, max_length=500)
    remove_source_ids: list[Identifier] = Field(default_factory=list, max_length=500)
    policy: PolicyName | None = None
    after_source_id: int = Field(default=0, ge=0, le=9223372036854775807)
    limit: int = Field(default=100, ge=1, le=250)

    @model_validator(mode="after")
    def changes_are_unambiguous(self):
        if set(self.add_source_ids) & set(self.remove_source_ids):
            raise ValueError("A source cannot be both added and removed")
        if not (self.add_source_ids or self.remove_source_ids or self.policy):
            raise ValueError("Provide sources or a policy")
        if self.policy and self.remove_source_ids:
            raise ValueError("Revoke selected sources in a separate request")
        return self


class Lease(PortableModel):
    lease_id: UUID


class Heartbeat(Lease):
    phase: Literal["capturing", "uploading"] | None = None


class UploadRequest(Lease):
    representation: Literal["rendered_dom"]
    content_hash: Digest
    content_size: Annotated[int, Field(strict=True, gt=0, le=MAX_BYTES)]
    mime_type: Literal["text/html"]


class SelectorReport(PortableModel):
    definition_fingerprint: Digest
    result: SelectorEvaluationResult


class Completion(UploadRequest):
    upload_intent_id: UUID
    completion_key: UUID
    representation_version: Literal["firefox-dom-1"]
    structure_hash_version: Literal["dom-shape-1"]
    hash_algorithm: Literal["sha256"]
    structure_hash: Digest
    page_url: URL
    captured_at: datetime
    evaluations: list[SelectorReport] = Field(max_length=MAX_SELECTORS)

    @model_validator(mode="after")
    def aware_capture(self):
        if self.captured_at.utcoffset() is None:
            raise ValueError("capturedAt must include a timezone")
        return self


class Failure(Lease):
    code: Literal[
        "NAVIGATION_FAILED",
        "PAGE_TIMEOUT",
        "HTTP_ERROR",
        "UNSUPPORTED_CONTENT_TYPE",
        "CAPTURE_FAILED",
        "UPLOAD_FAILED",
        "CANCELLED",
    ]


class PinnedSelector(PortableModel):
    selector_uuid: UUID
    version_uuid: UUID
    version_no: int
    definition_fingerprint: Digest
    definition: SelectorVersionDefinition


class TrustedNavigation(PortableModel):
    mode: Literal["trusted"] = "trusted"
    allow_http: bool


class ClaimedJob(PortableModel):
    job_id: UUID
    source_id: int
    url: str
    allowed_origins: list[str]
    reason: str
    lease_id: UUID
    lease_expires_at: datetime
    representation: Literal["rendered_dom"] = "rendered_dom"
    selectors: list[PinnedSelector]
    navigation: TrustedNavigation | None = None


class UploadURL(PortableModel):
    upload_intent_id: UUID
    url: str
    expires_at: datetime


class JobStatus(PortableModel):
    job_id: UUID
    source_id: int
    status: str
    attempt_count: int
    source_snapshot_id: int | None
    extraction_run_id: int | None
    error_code: str | None
