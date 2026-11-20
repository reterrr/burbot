"""Selector REST inputs keep portable identities separate from database bindings."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from extraction.schemas.api import Identifier, TokenClassId
from extraction.schemas.capture import CaptureResponse, ClientKey
from extraction.schemas.selector_tree import (
    Nonempty,
    PortableModel,
    PortableUUID,
    SelectorEvaluationResult,
    SelectorTree,
)

MAX_SNAPSHOT_BYTES = 5 * 1024 * 1024


class SelectorBinding(PortableModel):
    business_entity_field_id: Identifier
    source_id: Identifier | None = None
    business_object_field_id: Identifier | None = None


class SelectorImport(PortableModel):
    tree: SelectorTree
    binding: SelectorBinding | None = None
    snapshot_bindings: dict[PortableUUID, Identifier] = Field(default_factory=dict)


class SelectorReview(PortableModel):
    reviewed_by: Nonempty = None


class SelectorExecution(PortableModel):
    run_id: Identifier
    capture_key: ClientKey
    source_snapshot_id: Identifier | None = None
    token_class_id: TokenClassId = "text"
    html: str | None = Field(default=None, max_length=MAX_SNAPSHOT_BYTES)


class ClientEvaluation(PortableModel):
    uuid: PortableUUID | None = None
    page_url: Nonempty
    source_snapshot_id: Identifier | None = None
    result: SelectorEvaluationResult


class StoredEvaluation(PortableModel):
    uuid: PortableUUID
    evaluated_at: datetime
    page_url: str
    source_snapshot_id: int | None
    extraction_run_id: int | None
    provenance: Literal["client_reported", "backend_verified"]
    result: SelectorEvaluationResult


class SelectorExecutionResult(PortableModel):
    evaluation: StoredEvaluation
    capture: CaptureResponse | None
