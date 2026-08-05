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
    """Define persistence operations for token class records."""
    async def get_by_name(
        self,
        name: str,
        *,
        include_deleted: bool = False,
    ) -> TokenClass | None:
        """Retrieve a record by name.

        :param name: Human-readable or database type name, depending on context.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...


class TargetFieldRepository(SoftDeleteRepository[TargetField, int], Protocol):
    """Define persistence operations for target field records."""
    async def get_by_name(
        self,
        entity_type: BusinessEntityType,
        name: str,
        *,
        include_deleted: bool = False,
    ) -> TargetField | None:
        """Retrieve a record by name.

        :param entity_type: Entity type value.
        :param name: Human-readable or database type name, depending on context.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_for_entity(
        self,
        entity_type: BusinessEntityType,
        *,
        required_only: bool = False,
        include_deleted: bool = False,
    ) -> Sequence[TargetField]:
        """List records belonging to entity.

        :param entity_type: Entity type value.
        :param required_only: Required only value.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...


class ElementRepository(ReadRepository[Element, int], Protocol):
    """Define persistence operations for element records."""

    async def append(self, element: Element) -> Element:
        """Append an immutable record.

        :param element: Element value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def append_html(self, details: ElementHTML) -> ElementHTML:
        """Append html.

        :param details: Details value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def append_pdf(self, details: ElementPDF) -> ElementPDF:
        """Append pdf.

        :param details: Details value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def append_anchor(
        self,
        reference: AnchorElementReference,
    ) -> AnchorElementReference:
        """Append anchor.

        :param reference: Reference value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def append_value(self, value: ConcreteValue) -> ConcreteValue:
        """Append value.

        :param value: Raw value to normalize and validate.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def get_html(self, element_id: int) -> ElementHTML | None:
        """Retrieve html.

        :param element_id: Identifier of the element.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def get_pdf(self, element_id: int) -> ElementPDF | None:
        """Retrieve pdf.

        :param element_id: Identifier of the element.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_for_run(
        self,
        extraction_run_id: int,
        *,
        limit: int = 1000,
        offset: int = 0,
    ) -> Sequence[Element]:
        """List records belonging to run.

        :param extraction_run_id: Identifier of the extraction run.
        :param limit: Maximum number of records to return.
        :param offset: Number of matching records to skip.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def list_children(self, parent_element_id: int) -> Sequence[Element]:
        """List children.

        :param parent_element_id: Identifier of the parent element.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def list_values(
        self,
        element_id: int,
    ) -> Sequence[ConcreteValue]:
        """List values.

        :param element_id: Identifier of the element.
        :return: Matching records in deterministic repository order.
        """
        ...


class ScopeRepository(Protocol):
    """Define persistence operations for scope records."""

    async def get_scope(self, scope_id: int) -> SourceScope | None:
        """Retrieve scope.

        :param scope_id: Identifier of the scope.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def add_scope_version(self, scope: SourceScope) -> SourceScope:
        """Add scope version.

        :param scope: Scope value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def close_scope_version(self, scope_id: int) -> SourceScope | None:
        """Close scope version.

        :param scope_id: Identifier of the scope.
        :return: Result of the operation.
        """
        ...

    async def get_active_scope(
        self,
        source_id: int,
        name: str,
    ) -> SourceScope | None:
        """Retrieve active scope.

        :param source_id: Identifier of the source.
        :param name: Human-readable or database type name, depending on context.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_scopes(
        self,
        source_id: int,
        *,
        active_only: bool = True,
    ) -> Sequence[SourceScope]:
        """List scopes.

        :param source_id: Identifier of the source.
        :param active_only: Active only value.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def get_selector(self, selector_id: int) -> FieldSelector | None:
        """Retrieve selector.

        :param selector_id: Identifier of the selector.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def add_selector_version(
        self,
        selector: FieldSelector,
    ) -> FieldSelector:
        """Add selector version.

        :param selector: Selector value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def close_selector_version(
        self,
        selector_id: int,
    ) -> FieldSelector | None:
        """Close selector version.

        :param selector_id: Identifier of the selector.
        :return: Result of the operation.
        """
        ...

    async def get_active_selector(
        self,
        scope_id: int,
        target_field_id: int,
    ) -> FieldSelector | None:
        """Retrieve active selector.

        :param scope_id: Identifier of the scope.
        :param target_field_id: Identifier of the target field.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_selectors(
        self,
        scope_id: int,
        *,
        active_only: bool = True,
    ) -> Sequence[FieldSelector]:
        """List selectors.

        :param scope_id: Identifier of the scope.
        :param active_only: Active only value.
        :return: Matching records in deterministic repository order.
        """
        ...


class ScopeInstanceRepository(
    AppendOnlyRepository[ScopeInstance, int],
    Protocol,
):
    """Define persistence operations for scope instance records."""
    async def list_for_run(
        self,
        extraction_run_id: int,
        *,
        scope_id: int | None = None,
    ) -> Sequence[ScopeInstance]:
        """List records belonging to run.

        :param extraction_run_id: Identifier of the extraction run.
        :param scope_id: Identifier of the scope.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def list_children(
        self,
        parent_scope_instance_id: int,
    ) -> Sequence[ScopeInstance]:
        """List children.

        :param parent_scope_instance_id: Identifier of the parent scope instance.
        :return: Matching records in deterministic repository order.
        """
        ...


class FieldObservationRepository(
    CurrentStateRepository[FieldObservation, int],
    Protocol,
):
    """Define persistence operations for field observation records."""
    async def list_for_run(
        self,
        extraction_run_id: int,
        *,
        status: ObservationStatus | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> Sequence[FieldObservation]:
        """List records belonging to run.

        :param extraction_run_id: Identifier of the extraction run.
        :param status: Status value.
        :param limit: Maximum number of records to return.
        :param offset: Number of matching records to skip.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def list_for_scope_instance(
        self,
        scope_instance_id: int,
    ) -> Sequence[FieldObservation]:
        """List records belonging to scope instance.

        :param scope_instance_id: Identifier of the scope instance.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def list_for_entity(
        self,
        entity_type: BusinessEntityType,
        entity_id: int,
        *,
        status: ObservationStatus | None = None,
    ) -> Sequence[FieldObservation]:
        """List records belonging to entity.

        :param entity_type: Entity type value.
        :param entity_id: Identifier of the entity.
        :param status: Status value.
        :return: Matching records in deterministic repository order.
        """
        ...


class PhraseRepository(SoftDeleteRepository[Phrase, int], Protocol):
    """Define persistence operations for phrase records."""
    async def get_by_phrase(
        self,
        phrase: str,
        *,
        include_deleted: bool = False,
    ) -> Phrase | None:
        """Retrieve a record by phrase.

        :param phrase: Phrase value.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...


class SemanticClassRepository(
    SoftDeleteRepository[SemanticClass, int],
    Protocol,
):
    """Define persistence operations for semantic class records."""
    async def get_by_name(
        self,
        name: str,
        *,
        include_deleted: bool = False,
    ) -> SemanticClass | None:
        """Retrieve a record by name.

        :param name: Human-readable or database type name, depending on context.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...


class PhraseClassificationRepository(
    SoftDeleteRepository[PhraseClassification, int],
    Protocol,
):
    """Define persistence operations for phrase classification records."""
    async def list_for_phrase(
        self,
        phrase_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[PhraseClassification]:
        """List records belonging to phrase.

        :param phrase_id: Identifier of the phrase.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def list_for_semantic_class(
        self,
        semantic_class_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[PhraseClassification]:
        """List records belonging to semantic class.

        :param semantic_class_id: Identifier of the semantic class.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...


class PatternRepository(
    SoftDeleteRepository[GeneralizedPattern, int],
    Protocol,
):
    """Define persistence operations for pattern records."""

    async def get_by_class(
        self,
        pattern_type: PatternType,
        pattern_class: str,
        *,
        include_deleted: bool = False,
    ) -> GeneralizedPattern | None:
        """Retrieve a record by class.

        :param pattern_type: Pattern type value.
        :param pattern_class: Pattern class value.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_items(
        self,
        pattern_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[PatternItem]:
        """List items.

        :param pattern_id: Identifier of the pattern.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def add_item(self, item: PatternItem) -> PatternItem:
        """Add item.

        :param item: Item value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def save_item(self, item: PatternItem) -> PatternItem:
        """Persist changes to an existing record.

        :param item: Item value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def soft_delete_item(self, item_id: int) -> bool:
        """Soft-delete a record without removing its stored data.

        :param item_id: Identifier of the item.
        :return: ``True`` when the requested state change was applied.
        """
        ...

    async def restore_item(self, item_id: int) -> PatternItem | None:
        """Restore a soft-deleted record.

        :param item_id: Identifier of the item.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def append_instance(
        self,
        instance: PatternInstance,
    ) -> PatternInstance:
        """Append instance.

        :param instance: Instance value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def append_match(
        self,
        match: PatternInstanceMatch,
    ) -> PatternInstanceMatch:
        """Append match.

        :param match: Match value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def list_instances(
        self,
        pattern_id: int,
        *,
        extraction_run_id: int | None = None,
    ) -> Sequence[PatternInstance]:
        """List instances.

        :param pattern_id: Identifier of the pattern.
        :param extraction_run_id: Identifier of the extraction run.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def list_matches(
        self,
        pattern_instance_id: int,
    ) -> Sequence[PatternInstanceMatch]:
        """List matches.

        :param pattern_instance_id: Identifier of the pattern instance.
        :return: Matching records in deterministic repository order.
        """
        ...


class GroundTruthRepository(
    SoftDeleteRepository[GroundTruth, int],
    Protocol,
):
    """Define persistence operations for ground truth records."""
    async def list_for_source(
        self,
        source_id: int,
        *,
        target_field_id: int | None = None,
        include_deleted: bool = False,
    ) -> Sequence[GroundTruth]:
        """List records belonging to source.

        :param source_id: Identifier of the source.
        :param target_field_id: Identifier of the target field.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def list_for_entity(
        self,
        entity_type: BusinessEntityType,
        entity_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[GroundTruth]:
        """List records belonging to entity.

        :param entity_type: Entity type value.
        :param entity_id: Identifier of the entity.
        :param include_deleted: Whether soft-deleted records should be included.
        :return: Matching records in deterministic repository order.
        """
        ...
