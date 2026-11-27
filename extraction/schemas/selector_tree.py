"""Portable selector definitions and diagnostics shared with the Firefox extension."""

import re
from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from pydantic.alias_generators import to_camel

UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
    re.IGNORECASE,
)
MAX_SAFE_INTEGER = 2**53 - 1
MAX_RAW_LENGTH = 100_000
MAX_CANDIDATE_LENGTH = 4_096
MAX_BOUNDARY_LENGTH = 256
ELEMENT_LOCATOR_KINDS = {"css_path", "xpath", "element_id"}
JS_SPACE = (
    " \t\n\r\f\v\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006"
    "\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
)
SPACE_CHARACTERS = re.escape(JS_SPACE)
SENSITIVE_TEXT = re.compile(
    r"\b(?:[\w%-]*(?:token|password|passwd|secret|session|credential|auth|signature)"
    rf"[\w%-]*|code)[{SPACE_CHARACTERS}]*[:=][{SPACE_CHARACTERS}]*[^{SPACE_CHARACTERS}]"
    rf"|https?://[^{SPACE_CHARACTERS}/?#]*@|\bbearer[{SPACE_CHARACTERS}]+[\w.+/=-]+",
    re.ASCII | re.IGNORECASE,
)


def valid_uuid(value):
    if isinstance(value, UUID):
        value = str(value)
    if not isinstance(value, str) or not UUID_PATTERN.fullmatch(value):
        raise ValueError("Invalid selector UUID")
    return value


def safe_integer(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def timestamp(value: str) -> str:
    # Preserve the extension's exact serialized timestamp, including milliseconds.
    datetime.fromisoformat(value)
    return value


def utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def safe_candidate_text(value: str) -> bool:
    return (
        bool(value.strip(JS_SPACE))
        and "\x00" not in value
        and utf16_length(value) <= MAX_CANDIDATE_LENGTH
        and not SENSITIVE_TEXT.search(value)
    )


def text_boundary(value: str) -> str:
    if not value.strip(JS_SPACE) or "\x00" in value or utf16_length(value) > MAX_BOUNDARY_LENGTH:
        raise ValueError("Text boundaries must be nonempty and at most 256 characters")
    return value


PortableUUID = Annotated[UUID, BeforeValidator(valid_uuid)]
Nonempty = Annotated[str, StringConstraints(min_length=1)]
Timestamp = Annotated[str, AfterValidator(timestamp)]
Order = Annotated[int, Field(strict=True, ge=0, le=MAX_SAFE_INTEGER), BeforeValidator(safe_integer)]
VersionNo = Annotated[
    int, Field(strict=True, gt=0, le=MAX_SAFE_INTEGER), BeforeValidator(safe_integer)
]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]
VersionStatus = Literal["draft", "active", "superseded", "rejected"]
ArtifactType = Literal["raw_html", "rendered_dom"]
EvaluationStatus = Literal["success", "not_found", "ambiguous", "conflict", "error", "unsupported"]
ExtractionError = Literal[
    "selection_quote_mismatch",
    "selection_quote_ambiguous",
    "selection_context_mismatch",
    "selection_context_ambiguous",
    "text_boundary_missing",
    "text_boundary_ambiguous",
    "element_required",
    "attribute_missing",
    "empty_value",
    "value_too_large",
    "extraction_failed",
]
ERROR_EXTRACTION_TYPES = {
    "selection_quote_mismatch": "selection",
    "selection_quote_ambiguous": "selection",
    "selection_context_mismatch": "selection",
    "selection_context_ambiguous": "selection",
    "text_boundary_missing": "text_between",
    "text_boundary_ambiguous": "text_between",
    "attribute_missing": "attribute",
}


class PortableModel(BaseModel):
    model_config = ConfigDict(extra="forbid", alias_generator=to_camel, populate_by_name=True)

    def portable(self):
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)


class TargetIdentity(PortableModel):
    kind: Nonempty
    id: Nonempty


class SelectorTarget(PortableModel):
    object_id: Nonempty
    field: Nonempty
    target: TargetIdentity = None


class MigrationProvenance(PortableModel):
    legacy_rule_id: Nonempty
    provenance: Literal["unverified"]


class SelectorDefinition(PortableModel):
    uuid: PortableUUID
    target: SelectorTarget
    source_uuid: PortableUUID = None
    page_url: Nonempty = None
    active_version_uuid: PortableUUID | None = None
    created_at: Timestamp
    migration: MigrationProvenance = None


class TextQuote(PortableModel):
    exact: Nonempty
    prefix: str = None
    suffix: str = None


class TextSpec(PortableModel):
    type: Literal["text"]


class AttributeSpec(PortableModel):
    type: Literal["attribute"]
    name: Nonempty


class SelectionSpec(PortableModel):
    type: Literal["selection"]
    quote: TextQuote


class TextBetweenSpec(PortableModel):
    type: Literal["text_between"]
    start: Annotated[str, AfterValidator(text_boundary)]
    end: Annotated[str, AfterValidator(text_boundary)]


ExtractionSpec = Annotated[
    TextSpec | AttributeSpec | SelectionSpec | TextBetweenSpec, Field(discriminator="type")
]


class ReservedPayload(PortableModel):
    # The extension validates known keys within reserved payloads and preserves the rest.
    model_config = ConfigDict(extra="allow")


class DomSegment(ReservedPayload):
    tag_name: Nonempty
    sibling_index: Order


class DomPathPayload(ReservedPayload):
    root: Literal["document"]
    segments: list[DomSegment] = Field(min_length=1)


class DomBoundary(ReservedPayload):
    path: DomPathPayload
    text_node_index: Order
    offset: Order


class DomRangePayload(ReservedPayload):
    start: DomBoundary
    end: DomBoundary
    offset_unit: Literal["utf16_code_unit"]


class ContentHash(ReservedPayload):
    algorithm: Literal["sha256"]
    value: Digest


class TextCoordinates(ReservedPayload):
    representation: Literal["raw_html", "rendered_dom_text"]
    representation_version: Nonempty
    offset_unit: Literal["unicode_codepoint", "utf16_code_unit", "utf8_byte"]
    content_hash: ContentHash


class TextPositionPayload(ReservedPayload):
    start: Order
    end: Order
    coordinates: TextCoordinates

    @model_validator(mode="after")
    def bounds(self) -> Self:
        if self.end <= self.start:
            raise ValueError("Text position end must exceed start")
        return self


class ExactPositionPayload(TextPositionPayload):
    exact: Nonempty


class TextFragmentPayload(ReservedPayload):
    text_start: Nonempty
    text_end: str = None
    prefix: str = None
    suffix: str = None


class Locator(PortableModel):
    uuid: PortableUUID
    order: Order


class CssLocator(Locator):
    kind: Literal["css_path"]
    selector: Nonempty


class XPathLocator(Locator):
    kind: Literal["xpath"]
    expression: Nonempty


class ElementIdLocator(Locator):
    kind: Literal["element_id"]
    element_id: Nonempty


class TextQuoteLocator(Locator):
    kind: Literal["text_quote"]
    quote: TextQuote


class DomPathLocator(Locator):
    kind: Literal["dom_path"]
    payload: DomPathPayload


class DomRangeLocator(Locator):
    kind: Literal["dom_range"]
    payload: DomRangePayload


class ExactPositionLocator(Locator):
    kind: Literal["exact_pos"]
    payload: ExactPositionPayload


class TextPositionLocator(Locator):
    kind: Literal["text_position"]
    payload: TextPositionPayload


class TextFragmentLocator(Locator):
    kind: Literal["text_fragment"]
    payload: TextFragmentPayload


SelectorLocator = Annotated[
    CssLocator
    | XPathLocator
    | ElementIdLocator
    | TextQuoteLocator
    | DomPathLocator
    | DomRangeLocator
    | ExactPositionLocator
    | TextPositionLocator
    | TextFragmentLocator,
    Field(discriminator="kind"),
]


def ordered(items):
    return sorted(items, key=lambda item: item.order)


def distinct(items, key, label):
    result = {getattr(item, key): item for item in items}
    if len(result) != len(items):
        raise ValueError(f"Duplicate {label}")
    return result


class SelectorPart(PortableModel):
    uuid: PortableUUID
    order: Order
    extraction: ExtractionSpec
    locators: list[SelectorLocator] = Field(min_length=1)
    join_with: str = None

    @model_validator(mode="after")
    def element_boundaries(self) -> Self:
        if self.extraction.type == "text_between" and not any(
            locator.kind in ELEMENT_LOCATOR_KINDS for locator in self.locators
        ):
            raise ValueError("Text boundaries require an element locator")
        return self


class SelectorRecipe(PortableModel):
    uuid: PortableUUID
    order: Order
    parts: list[SelectorPart] = Field(min_length=1)


class SelectorVersionDefinition(PortableModel):
    uuid: PortableUUID
    selector_uuid: PortableUUID
    version_no: VersionNo
    status: VersionStatus
    created_from_snapshot_uuid: PortableUUID | None = None
    artifact_type: ArtifactType | None = None
    recipes: list[SelectorRecipe] = Field(min_length=1)
    created_at: Timestamp
    reviewed_at: Timestamp = None
    reviewed_by: Nonempty = None


class SelectorTree(PortableModel):
    selector: SelectorDefinition
    versions: list[SelectorVersionDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def graph(self) -> Self:
        ids = {self.selector.uuid}

        def add(item):
            if item.uuid in ids:
                raise ValueError("Duplicate UUID in selector tree")
            ids.add(item.uuid)

        distinct(self.versions, "version_no", "version number")
        for version in self.versions:
            add(version)
            if version.selector_uuid != self.selector.uuid:
                raise ValueError("Version belongs to another selector")
            distinct(version.recipes, "order", "recipe order")
            for recipe in version.recipes:
                add(recipe)
                distinct(recipe.parts, "order", "part order")
                for part in recipe.parts:
                    add(part)
                    distinct(part.locators, "order", "locator order")
                    for locator in part.locators:
                        add(locator)
        active = [version.uuid for version in self.versions if version.status == "active"]
        if active != (
            [self.selector.active_version_uuid] if self.selector.active_version_uuid else []
        ):
            raise ValueError("Active version reference does not match its status")
        return self

    def canonical_order(self) -> Self:
        """Use the same deterministic order as the extension's SQL export."""
        self.versions.sort(key=lambda version: version.version_no)
        for version in self.versions:
            version.recipes = ordered(version.recipes)
            for recipe in version.recipes:
                recipe.parts = ordered(recipe.parts)
                for part in recipe.parts:
                    part.locators = ordered(part.locators)
        return self


def validate_selector_transition(before: SelectorTree, after: SelectorTree) -> None:
    if (
        before.selector.uuid != after.selector.uuid
        or before.selector.target != after.selector.target
    ):
        raise ValueError("Selector identity and target cannot change")
    previous = distinct(before.versions, "uuid", "version")
    incoming = distinct(after.versions, "uuid", "version")
    for identity, old in previous.items():
        new = incoming.get(identity)
        if new is None:
            raise ValueError("Selector version history cannot be removed")
        if new.version_no != old.version_no:
            raise ValueError("Version number cannot change")
        if old.status == "draft":
            if new.status == "superseded" and not new.reviewed_at:
                raise ValueError("Superseding a draft requires review metadata")
        else:
            status = (
                "superseded"
                if old.status == "active" and new.status == "superseded"
                else old.status
            )
            if new.portable() != {**old.portable(), "status": status}:
                raise ValueError("Approved selector versions are immutable; create a draft")
    maximum = max(version.version_no for version in before.versions)
    for identity in incoming.keys() - previous.keys():
        new = incoming[identity]
        if new.version_no <= maximum or (new.status != "draft" and not new.reviewed_at):
            raise ValueError("New versions require a new version number and explicit review")


class Evaluation(PortableModel):
    status: EvaluationStatus
    raw_value: str = None
    diagnostic: str = None

    @model_validator(mode="after")
    def bounded_success(self) -> Self:
        if self.status == "success" and (
            not self.raw_value or utf16_length(self.raw_value) > MAX_RAW_LENGTH
        ):
            raise ValueError("Successful evaluation requires a bounded value")
        return self


class DiagnosticCandidate(PortableModel):
    raw_text: str
    source: Literal["matched_element_text"]
    verified: Literal[False]

    @model_validator(mode="before")
    @classmethod
    def explicitly_unverified(cls, values):
        # Literal[False] alone also accepts the integer 0.
        if isinstance(values, dict) and values.get("verified") is not False:
            raise ValueError("A diagnostic candidate must be explicitly unverified")
        return values

    @model_validator(mode="after")
    def bounded_text(self) -> Self:
        if not safe_candidate_text(self.raw_text):
            raise ValueError("A diagnostic candidate requires bounded, non-sensitive text")
        return self


class LocatorEvaluationResult(Evaluation):
    locator_uuid: PortableUUID
    match_count: Order
    extraction_error: ExtractionError = None
    candidate: DiagnosticCandidate = None

    @model_validator(mode="after")
    def extraction_result(self) -> Self:
        if self.status == "success" and self.match_count != 1:
            raise ValueError("A successful locator requires a unique match")
        if self.extraction_error is not None and (
            self.status != "error" or self.match_count != 1 or self.raw_value is not None
        ):
            raise ValueError("An extraction error requires one located target and no raw value")
        if self.candidate is not None and self.extraction_error is None:
            raise ValueError("A diagnostic candidate requires an extraction error")
        return self


class PartEvaluationResult(Evaluation):
    part_uuid: PortableUUID
    locator_results: list[LocatorEvaluationResult]


class RecipeEvaluationResult(Evaluation):
    recipe_uuid: PortableUUID
    part_results: list[PartEvaluationResult]


class SelectorEvaluationResult(Evaluation):
    selector_version_uuid: PortableUUID
    recipe_results: list[RecipeEvaluationResult]


def validate_selector_evaluation(
    result: SelectorEvaluationResult, version: SelectorVersionDefinition
):
    if result.selector_version_uuid != version.uuid:
        raise ValueError("Evaluation belongs to another version")

    def children(results, definitions, key):
        mapping = distinct(results, key, "evaluation component")
        if mapping.keys() != {item.uuid for item in definitions}:
            raise ValueError("Incomplete evaluation diagnostics or unknown component UUID")
        return ((mapping[item.uuid], item) for item in definitions)

    for recipe_result, recipe in children(result.recipe_results, version.recipes, "recipe_uuid"):
        for part_result, part in children(recipe_result.part_results, recipe.parts, "part_uuid"):
            for reported, locator in children(
                part_result.locator_results, part.locators, "locator_uuid"
            ):
                expected_type = ERROR_EXTRACTION_TYPES.get(reported.extraction_error)
                if expected_type is not None and expected_type != part.extraction.type:
                    raise ValueError(
                        "Locator extraction error does not match its configured method"
                    )
                if reported.extraction_error == "element_required" and (
                    locator.kind != "text_quote"
                    or part.extraction.type not in {"attribute", "text_between"}
                ):
                    raise ValueError("Locator and extraction method do not require an element")
                if reported.candidate is not None and locator.kind not in ELEMENT_LOCATOR_KINDS:
                    raise ValueError("A diagnostic candidate requires an element locator")
