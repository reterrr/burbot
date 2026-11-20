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


ExtractionSpec = Annotated[TextSpec | AttributeSpec | SelectionSpec, Field(discriminator="type")]


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


class LocatorEvaluationResult(Evaluation):
    locator_uuid: PortableUUID
    match_count: Order

    @model_validator(mode="after")
    def unique_match(self) -> Self:
        if self.status == "success" and self.match_count != 1:
            raise ValueError("A successful locator requires a unique match")
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
            list(children(part_result.locator_results, part.locators, "locator_uuid"))
