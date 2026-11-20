"""Browser Agent wire contracts and versioned snapshot representation."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StringConstraints, model_validator

from extraction.schemas.api import Identifier
from extraction.schemas.selector_tree import (
    PortableModel,
    SelectorEvaluationResult,
    SelectorVersionDefinition,
)

REPRESENTATION = "rendered_dom"
REPRESENTATION_VERSION = "firefox-dom-1"
STRUCTURE_HASH_VERSION = "dom-shape-1"
MIME_TYPE = "text/html"
MAX_BYTES = 5 * 1024 * 1024
MAX_SELECTORS = 64

Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
URL = Annotated[str, StringConstraints(min_length=1, max_length=2048)]


class Approval(PortableModel):
    enabled: bool = True
    additional_origins: list[URL] = Field(default_factory=list, max_length=20)


class RegisterAgent(PortableModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
    source_ids: list[Identifier] = Field(min_length=1, max_length=250)


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
        "NAVIGATION_FAILED", "PAGE_TIMEOUT", "CAPTURE_FAILED", "UPLOAD_FAILED", "CANCELLED"
    ]


class PinnedSelector(PortableModel):
    selector_uuid: UUID
    version_uuid: UUID
    version_no: int
    definition_fingerprint: Digest
    definition: SelectorVersionDefinition


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
