"""Batch DTOs: definitions, occurrences, literals and interpretations have distinct keys."""

from datetime import datetime
from graphlib import CycleError, TopologicalSorter
from typing import Annotated, Any, Self

from pydantic import Field, StringConstraints, model_validator

from extraction.schemas.api import Identifier, NonBlank, RequestModel, ResponseModel, TokenClassId
from extraction.schemas.enums import (
    AnchorRelationKind,
    DiscoveryMethod,
    ElementFrom,
    ExtractionIssueCode,
    ExtractionRunStatus,
    ObservationStatus,
    SelectorType,
)

ClientKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Coordinate = Annotated[float, Field(allow_inf_nan=False)]


class CreateRunRequest(RequestModel):
    snapshot_id: Identifier
    extractor_version: ClientKey
    workflow_id: Identifier | None = None


class RunResponse(ResponseModel):
    id: int
    snapshot_id: int
    source_id: int
    workflow_id: int | None
    status: ExtractionRunStatus
    extractor_version: str | None
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime


class TokenClassRequest(RequestModel):
    id: TokenClassId
    name: ClientKey
    validation_regex: str | None = None
    parser_name: ClientKey | None = None
    description: str | None = None


class SelectorRequest(RequestModel):
    type: SelectorType
    value: NonBlank
    confidence: Confidence = 1.0
    discovered_by: DiscoveryMethod = DiscoveryMethod.MANUAL


class HTMLMetadata(RequestModel):
    dom_path: str | None = None
    absolute_xpath: str | None = None
    css_path: str | None = None
    tag_name: str | None = None
    attributes_json: dict[str, Any] | None = None


class PDFMetadata(RequestModel):
    page_number: int = Field(gt=0)
    x0: Coordinate | None = None
    y0: Coordinate | None = None
    x1: Coordinate | None = None
    y1: Coordinate | None = None
    block_number: int | None = Field(default=None, ge=0)
    line_number: int | None = Field(default=None, ge=0)
    word_number: int | None = Field(default=None, ge=0)
    font_name: str | None = None
    font_size: Coordinate | None = Field(default=None, gt=0)
    ocr_confidence: Confidence | None = None

    @model_validator(mode="after")
    def bounds(self) -> Self:
        for a, b in ((self.x0, self.x1), (self.y0, self.y1)):
            if (a is None) != (b is None) or (a is not None and b < a):
                raise ValueError("PDF bounds must be supplied as ordered coordinate pairs")
        return self


class XLSXMetadata(RequestModel):
    sheet_name: ClientKey
    cell_range: Annotated[
        str, StringConstraints(pattern=r"^\$?[A-Z]+\$?[1-9][0-9]*(?::\$?[A-Z]+\$?[1-9][0-9]*)?$")
    ]


class ElementRequest(RequestModel):
    client_key: ClientKey
    parent_client_key: ClientKey | None = None
    child_index: int | None = Field(default=None, ge=0)
    depth: int | None = Field(default=None, ge=0)
    element_from: ElementFrom
    text_content: str | None = None
    structural_hash: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")] | None = None
    html: HTMLMetadata | None = None
    pdf: PDFMetadata | None = None
    xlsx: XLSXMetadata | None = None

    @model_validator(mode="after")
    def subtype(self) -> Self:
        present = [
            name.upper() for name in ("html", "pdf", "xlsx") if getattr(self, name) is not None
        ]
        if present != [self.element_from]:
            raise ValueError("Provide exactly the metadata matching element_from")
        return self


class ScopeRequest(RequestModel):
    client_key: ClientKey
    parent_client_key: ClientKey | None = None
    name: ClientKey
    business_entity_id: Identifier | None = None
    selector: SelectorRequest


class ScopeInstanceRequest(RequestModel):
    client_key: ClientKey
    scope_client_key: ClientKey
    parent_client_key: ClientKey | None = None
    root_element_client_key: ClientKey
    occurrence_index: int = Field(default=0, ge=0)
    instance_hash: Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")] | None = None
    confidence: Confidence = 1.0
    business_object_id: Identifier | None = None


class ValueRequest(RequestModel):
    client_key: ClientKey
    scope_instance_client_key: ClientKey
    element_client_key: ClientKey
    business_entity_field_id: Identifier
    business_object_id: Identifier | None = None
    token_class_id: TokenClassId
    raw_value: str = Field(min_length=1)
    normalized_value: str | None = None
    is_semantic_null: bool = False
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    confidence: Confidence = 1.0
    discovered_by: DiscoveryMethod = DiscoveryMethod.MANUAL
    selector: SelectorRequest | None = None
    confirmed_by_human: bool = False
    supersedes_observation_id: Identifier | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def literal(self) -> Self:
        if not self.raw_value.strip():
            raise ValueError("raw_value must contain explicit source evidence")
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("char_start and char_end must be supplied together")
        if self.char_start is not None and self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        if self.is_semantic_null and self.normalized_value is not None:
            raise ValueError("Explicit semantic null cannot have a normalized value")
        return self


class AnchorRequest(RequestModel):
    anchor_element_client_key: ClientKey
    target_element_client_key: ClientKey
    relation_kind: AnchorRelationKind
    relative_offset: int | None = None
    confidence: Confidence | None = None


class IssueRequest(RequestModel):
    code: ExtractionIssueCode
    message: NonBlank
    scope_instance_client_key: ClientKey | None = None
    business_entity_field_id: Identifier | None = None


def keyed(items, label):
    result = {item.client_key: item for item in items}
    if len(result) != len(items):
        raise ValueError(f"Duplicate {label} client_key")
    return result


def ordered(items, label):
    by_key = keyed(items, label)
    graph = {}
    for key, item in by_key.items():
        parent = item.parent_client_key
        if parent is not None and parent not in by_key:
            raise ValueError(f"Unknown {label} parent_client_key: {parent}")
        graph[key] = [parent] if parent else []
    try:
        return [by_key[key] for key in TopologicalSorter(graph).static_order()]
    except CycleError as error:
        raise ValueError(f"Cycle in {label} parent references") from error


class CaptureRequest(RequestModel):
    capture_key: ClientKey
    scopes: list[ScopeRequest] = Field(min_length=1, max_length=500)
    scope_instances: list[ScopeInstanceRequest] = Field(min_length=1, max_length=5000)
    elements: list[ElementRequest] = Field(min_length=1, max_length=10000)
    values: list[ValueRequest] = Field(default_factory=list, max_length=10000)
    anchors: list[AnchorRequest] = Field(default_factory=list, max_length=10000)
    issues: list[IssueRequest] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def graph(self) -> Self:
        scopes = keyed(self.scopes, "scope")
        instances = keyed(self.scope_instances, "scope instance")
        elements = keyed(self.elements, "element")
        keyed(self.values, "value")
        for items, name in (
            (self.scopes, "scope"),
            (self.scope_instances, "scope instance"),
            (self.elements, "element"),
        ):
            ordered(items, name)
        roots = [s for s in self.scopes if s.parent_client_key is None]
        if len(roots) != 1 or roots[0].name != "ROOT":
            raise ValueError("Provide exactly one parentless scope named ROOT")
        if len({s.name for s in self.scopes}) != len(self.scopes):
            raise ValueError(
                "Scope definitions need distinct names; use scope_instances for repeats"
            )
        root_instances = []
        occurrences = set()
        matched_roots = set()
        for instance in self.scope_instances:
            scope = scopes.get(instance.scope_client_key)
            if scope is None or instance.root_element_client_key not in elements:
                raise ValueError("Scope instance references an unknown scope or root element")
            parent = instances.get(instance.parent_client_key)
            if (scope.parent_client_key is None) != (parent is None):
                raise ValueError("Scope instance parent must match its scope definition parent")
            if parent is not None and parent.scope_client_key != scope.parent_client_key:
                raise ValueError("Scope instance parent belongs to the wrong scope")
            if parent is None:
                root_instances.append(instance)
            occurrence = (
                instance.scope_client_key,
                instance.parent_client_key,
                instance.occurrence_index,
            )
            root = (instance.scope_client_key, instance.root_element_client_key)
            if occurrence in occurrences or root in matched_roots:
                raise ValueError("Duplicate scope occurrence or matched root")
            occurrences.add(occurrence)
            matched_roots.add(root)
        if len(root_instances) != 1:
            raise ValueError("The ROOT scope must have exactly one instance")
        value_fields = set()
        for value in self.values:
            identity = (value.scope_instance_client_key, value.business_entity_field_id)
            if identity in value_fields:
                raise ValueError("Duplicate field interpretation in a scope occurrence")
            value_fields.add(identity)
            if (
                value.scope_instance_client_key not in instances
                or value.element_client_key not in elements
            ):
                raise ValueError(
                    f"Value {value.client_key} references an unknown instance or element"
                )
        for anchor in self.anchors:
            if (
                anchor.anchor_element_client_key not in elements
                or anchor.target_element_client_key not in elements
            ):
                raise ValueError("Anchor references an unknown element")
        for issue in self.issues:
            if (
                issue.scope_instance_client_key is not None
                and issue.scope_instance_client_key not in instances
            ):
                raise ValueError("Issue references an unknown scope instance")
        if not self.values and not self.issues:
            raise ValueError("Capture must contain evidence or an explicit extraction issue")
        return self


class CaptureResponse(ResponseModel):
    run_id: int
    status: ExtractionRunStatus
    scopes_created: int
    observations_created: int
    scope_ids_by_client_key: dict[str, int]
    scope_instance_ids_by_client_key: dict[str, int]
    element_ids_by_client_key: dict[str, int]
    observation_ids_by_client_key: dict[str, int]
    resolved_observations: list[int]
    unresolved_observations: list[int]
    reconciliation_observations: list[int]
    changed_source_object_fields: list[int]
    issues: list[IssueRequest]


class ResolveObjectRequest(RequestModel):
    business_object_id: Identifier


class ObservationResponse(ResponseModel):
    id: int
    extraction_run_id: int
    source_field_tracking_id: int
    source_object_field_tracking_id: int | None
    business_object_id: int | None
    business_object_field_id: int | None
    scope_instance_id: int | None
    concrete_value_id: int | None
    status: ObservationStatus
    confidence: float
    observed_at: datetime
    validated_at: datetime | None
    supersedes_observation_id: int | None
    notes: str | None


class ExecuteRequest(RequestModel):
    capture_key: ClientKey


class CapturedLiteralResponse(ResponseModel):
    id: int
    element_id: int | None
    source_snapshot_id: int
    token_class_id: str
    raw_value: str
    normalized_value: str | None
    is_semantic_null: bool
    char_start: int | None
    char_end: int | None
    confidence: float
    discovered_by: str


class ObservationEvidenceResponse(ObservationResponse):
    concrete_values: list[CapturedLiteralResponse]
