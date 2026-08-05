"""Repository interfaces for extraction definitions and runtime provenance."""

from collections.abc import Sequence
from typing import Protocol

from ..db import (
    AnchorElementReference,
    ConcreteValue,
    Element,
    ElementHTML,
    ElementPDF,
    FieldObservation,
    FieldSelector,
    GeneralizedPattern,
    GroundTruth,
    PatternInstance,
    PatternInstanceMatch,
    PatternItem,
    Phrase,
    PhraseClassification,
    ScopeInstance,
    SemanticClass,
    SourceScope,
    TargetField,
    TokenClass,
)
from ..db.enums import (
    BusinessEntityType,
    ObservationStatus,
    PatternType,
)
from .base import (
    AppendOnlyRepository,
    CurrentStateRepository,
    ReadRepository,
    SoftDeleteRepository,
)


class TokenClassRepository(SoftDeleteRepository[TokenClass, int], Protocol):
    async def get_by_name(
        self,
        name: str,
        *,
        include_deleted: bool = False,
    ) -> TokenClass | None: ...


class TargetFieldRepository(SoftDeleteRepository[TargetField, int], Protocol):
    async def get_by_name(
        self,
        entity_type: BusinessEntityType,
        name: str,
        *,
        include_deleted: bool = False,
    ) -> TargetField | None: ...

    async def list_for_entity(
        self,
        entity_type: BusinessEntityType,
        *,
        required_only: bool = False,
        include_deleted: bool = False,
    ) -> Sequence[TargetField]: ...


class ElementRepository(ReadRepository[Element, int], Protocol):
    """Append-only element tree, subtypes, anchors and concrete values."""

    async def append(self, element: Element) -> Element: ...

    async def append_html(self, details: ElementHTML) -> ElementHTML: ...

    async def append_pdf(self, details: ElementPDF) -> ElementPDF: ...

    async def append_anchor(
        self,
        reference: AnchorElementReference,
    ) -> AnchorElementReference: ...

    async def append_value(self, value: ConcreteValue) -> ConcreteValue: ...

    async def get_html(self, element_id: int) -> ElementHTML | None: ...

    async def get_pdf(self, element_id: int) -> ElementPDF | None: ...

    async def list_for_run(
        self,
        extraction_run_id: int,
        *,
        limit: int = 1000,
        offset: int = 0,
    ) -> Sequence[Element]: ...

    async def list_children(self, parent_element_id: int) -> Sequence[Element]: ...

    async def list_values(
        self,
        element_id: int,
    ) -> Sequence[ConcreteValue]: ...


class ScopeRepository(Protocol):
    """Versioned source scopes and field selectors."""

    async def get_scope(self, scope_id: int) -> SourceScope | None: ...

    async def add_scope_version(self, scope: SourceScope) -> SourceScope: ...

    async def close_scope_version(self, scope_id: int) -> SourceScope | None: ...

    async def get_active_scope(
        self,
        source_id: int,
        name: str,
    ) -> SourceScope | None: ...

    async def list_scopes(
        self,
        source_id: int,
        *,
        active_only: bool = True,
    ) -> Sequence[SourceScope]: ...

    async def get_selector(self, selector_id: int) -> FieldSelector | None: ...

    async def add_selector_version(
        self,
        selector: FieldSelector,
    ) -> FieldSelector: ...

    async def close_selector_version(
        self,
        selector_id: int,
    ) -> FieldSelector | None: ...

    async def get_active_selector(
        self,
        scope_id: int,
        target_field_id: int,
    ) -> FieldSelector | None: ...

    async def list_selectors(
        self,
        scope_id: int,
        *,
        active_only: bool = True,
    ) -> Sequence[FieldSelector]: ...


class ScopeInstanceRepository(
    AppendOnlyRepository[ScopeInstance, int],
    Protocol,
):
    async def list_for_run(
        self,
        extraction_run_id: int,
        *,
        scope_id: int | None = None,
    ) -> Sequence[ScopeInstance]: ...

    async def list_children(
        self,
        parent_scope_instance_id: int,
    ) -> Sequence[ScopeInstance]: ...


class FieldObservationRepository(
    CurrentStateRepository[FieldObservation, int],
    Protocol,
):
    async def list_for_run(
        self,
        extraction_run_id: int,
        *,
        status: ObservationStatus | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> Sequence[FieldObservation]: ...

    async def list_for_scope_instance(
        self,
        scope_instance_id: int,
    ) -> Sequence[FieldObservation]: ...

    async def list_for_entity(
        self,
        entity_type: BusinessEntityType,
        entity_id: int,
        *,
        status: ObservationStatus | None = None,
    ) -> Sequence[FieldObservation]: ...


class PhraseRepository(SoftDeleteRepository[Phrase, int], Protocol):
    async def get_by_phrase(
        self,
        phrase: str,
        *,
        include_deleted: bool = False,
    ) -> Phrase | None: ...


class SemanticClassRepository(
    SoftDeleteRepository[SemanticClass, int],
    Protocol,
):
    async def get_by_name(
        self,
        name: str,
        *,
        include_deleted: bool = False,
    ) -> SemanticClass | None: ...


class PhraseClassificationRepository(
    SoftDeleteRepository[PhraseClassification, int],
    Protocol,
):
    async def list_for_phrase(
        self,
        phrase_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[PhraseClassification]: ...

    async def list_for_semantic_class(
        self,
        semantic_class_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[PhraseClassification]: ...


class PatternRepository(
    SoftDeleteRepository[GeneralizedPattern, int],
    Protocol,
):
    """Pattern definitions/items plus append-only runtime pattern matches."""

    async def get_by_class(
        self,
        pattern_type: PatternType,
        pattern_class: str,
        *,
        include_deleted: bool = False,
    ) -> GeneralizedPattern | None: ...

    async def list_items(
        self,
        pattern_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[PatternItem]: ...

    async def add_item(self, item: PatternItem) -> PatternItem: ...

    async def save_item(self, item: PatternItem) -> PatternItem: ...

    async def soft_delete_item(self, item_id: int) -> bool: ...

    async def restore_item(self, item_id: int) -> PatternItem | None: ...

    async def append_instance(
        self,
        instance: PatternInstance,
    ) -> PatternInstance: ...

    async def append_match(
        self,
        match: PatternInstanceMatch,
    ) -> PatternInstanceMatch: ...

    async def list_instances(
        self,
        pattern_id: int,
        *,
        extraction_run_id: int | None = None,
    ) -> Sequence[PatternInstance]: ...

    async def list_matches(
        self,
        pattern_instance_id: int,
    ) -> Sequence[PatternInstanceMatch]: ...


class GroundTruthRepository(
    SoftDeleteRepository[GroundTruth, int],
    Protocol,
):
    async def list_for_source(
        self,
        source_id: int,
        *,
        target_field_id: int | None = None,
        include_deleted: bool = False,
    ) -> Sequence[GroundTruth]: ...

    async def list_for_entity(
        self,
        entity_type: BusinessEntityType,
        entity_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[GroundTruth]: ...
