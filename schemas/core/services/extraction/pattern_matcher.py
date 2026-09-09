"""Match generalized patterns against classified extraction evidence."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from schemas.core.db import GeneralizedPattern, PatternItem
from schemas.core.db.enums import (
    ItemKind,
    ItemsetRole,
    PatternType,
)


class InvalidPatternError(ValueError):
    """Raised when a generalized pattern has an invalid definition."""


@dataclass(frozen=True, slots=True)
class PatternEvidence:
    """Describe classified evidence found in one sources element.

    :ivar element_id: Identifier of the sources element.
    :ivar order: Position of the evidence inside the current scope instance.
    :ivar token_class_ids: Token classes detected in the element.
    :ivar phrase_ids: Phrases detected in the element.
    :ivar semantic_class_ids: Semantic classes detected in the element.
    :ivar confidence: Evidence confidence between zero and one.
    """

    element_id: int
    order: int

    token_class_ids: frozenset[int] = field(default_factory=frozenset)
    phrase_ids: frozenset[int] = field(default_factory=frozenset)
    semantic_class_ids: frozenset[int] = field(default_factory=frozenset)

    confidence: float = 1.0

    def __post_init__(self) -> None:
        if self.order < 0:
            raise ValueError("Evidence order cannot be negative.")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "Evidence confidence must be between zero and one."
            )


@dataclass(frozen=True, slots=True)
class MatchedPatternItem:
    """Describe one pattern item matched against sources evidence."""

    pattern_item_id: int | None
    element_id: int
    pattern_position: int | None
    evidence_order: int
    confidence: float


@dataclass(frozen=True, slots=True)
class PatternMatch:
    """Represent a successful generalized-pattern match."""

    pattern_id: int
    target_field_ids: tuple[int, ...]
    matched_items: tuple[MatchedPatternItem, ...]
    confidence: float

    @property
    def element_ids(self) -> tuple[int, ...]:
        """Return unique matched element identifiers in matching order."""

        return tuple(
            dict.fromkeys(
                item.element_id
                for item in self.matched_items
            )
        )


class PatternMatcher:
    """Match sequential and associative generalized patterns."""

    def match(
        self,
        *,
        pattern: GeneralizedPattern,
        items: Sequence[PatternItem],
        evidence: Sequence[PatternEvidence],
    ) -> PatternMatch | None:
        """Match one generalized pattern against one scope instance.

        :param pattern: Generalized pattern to evaluate.
        :param items: Items belonging to the generalized pattern.
        :param evidence: Classified evidence from one scope instance.
        :return: Successful match or ``None``.
        :raises InvalidPatternError: If the pattern definition is invalid.
        """

        pattern_id = self._require_pattern_id(pattern)

        active_items = tuple(
            item
            for item in items
            if item.deleted_at is None
        )

        self._validate_pattern_items(
            pattern_id=pattern_id,
            items=active_items,
        )

        target_field_ids = self._get_target_field_ids(active_items)

        if not target_field_ids:
            raise InvalidPatternError(
                f"Pattern {pattern_id} does not define a target field."
            )

        source_items = tuple(
            item
            for item in active_items
            if item.item_kind != ItemKind.TARGET_FIELD
        )

        if not source_items:
            raise InvalidPatternError(
                f"Pattern {pattern_id} does not contain matchable items."
            )

        if pattern.pattern_type == PatternType.SEQUENTIAL:
            matched_items = self._match_sequential(
                items=source_items,
                evidence=evidence,
            )
        elif pattern.pattern_type == PatternType.ASSOCIATIVE:
            matched_items = self._match_associative(
                items=source_items,
                evidence=evidence,
            )
        else:
            raise InvalidPatternError(
                f"Unsupported pattern type: {pattern.pattern_type}."
            )

        if matched_items is None:
            return None

        confidence = self._calculate_confidence(
            pattern=pattern,
            matched_items=matched_items,
        )

        return PatternMatch(
            pattern_id=pattern_id,
            target_field_ids=target_field_ids,
            matched_items=matched_items,
            confidence=confidence,
        )

    def _match_sequential(
        self,
        *,
        items: Sequence[PatternItem],
        evidence: Sequence[PatternEvidence],
    ) -> tuple[MatchedPatternItem, ...] | None:
        ordered_items = sorted(
            items,
            key=self._require_pattern_position,
        )

        positions = [
            self._require_pattern_position(item)
            for item in ordered_items
        ]

        if len(positions) != len(set(positions)):
            raise InvalidPatternError(
                "Sequential pattern contains duplicate positions."
            )

        ordered_evidence = sorted(
            evidence,
            key=lambda item: item.order,
        )

        matched: list[MatchedPatternItem] = []
        evidence_index = 0

        for pattern_item in ordered_items:
            while evidence_index < len(ordered_evidence):
                candidate = ordered_evidence[evidence_index]
                evidence_index += 1

                if not self._matches_item(pattern_item, candidate):
                    continue

                matched.append(
                    self._create_item_match(
                        pattern_item=pattern_item,
                        evidence=candidate,
                    )
                )
                break
            else:
                return None

        return tuple(matched)

    def _match_associative(
        self,
        *,
        items: Sequence[PatternItem],
        evidence: Sequence[PatternEvidence],
    ) -> tuple[MatchedPatternItem, ...] | None:
        matched: list[MatchedPatternItem] = []

        for pattern_item in items:
            if pattern_item.role != ItemsetRole.ANTECEDENT:
                raise InvalidPatternError(
                    "Non-target items in an associative pattern must have "
                    "the ANTECEDENT role."
                )

            candidates = [
                candidate
                for candidate in evidence
                if self._matches_item(pattern_item, candidate)
            ]

            if not candidates:
                return None

            best_candidate = max(
                candidates,
                key=lambda candidate: candidate.confidence,
            )

            matched.append(
                self._create_item_match(
                    pattern_item=pattern_item,
                    evidence=best_candidate,
                )
            )

        return tuple(matched)

    @staticmethod
    def _matches_item(
        pattern_item: PatternItem,
        evidence: PatternEvidence,
    ) -> bool:
        if pattern_item.item_kind == ItemKind.TOKEN_CLASS:
            return (
                pattern_item.token_class_id is not None
                and pattern_item.token_class_id
                in evidence.token_class_ids
            )

        if pattern_item.item_kind == ItemKind.PHRASE:
            return (
                pattern_item.phrase_id is not None
                and pattern_item.phrase_id in evidence.phrase_ids
            )

        if pattern_item.item_kind == ItemKind.SEMANTIC_CLASS:
            return (
                pattern_item.semantic_class_id is not None
                and pattern_item.semantic_class_id
                in evidence.semantic_class_ids
            )

        if pattern_item.item_kind == ItemKind.TARGET_FIELD:
            raise InvalidPatternError(
                "Target fields cannot be matched against sources evidence."
            )

        raise InvalidPatternError(
            f"Unsupported pattern item kind: {pattern_item.item_kind}."
        )

    @staticmethod
    def _create_item_match(
        *,
        pattern_item: PatternItem,
        evidence: PatternEvidence,
    ) -> MatchedPatternItem:
        return MatchedPatternItem(
            pattern_item_id=pattern_item.id,
            element_id=evidence.element_id,
            pattern_position=pattern_item.position,
            evidence_order=evidence.order,
            confidence=evidence.confidence,
        )

    @staticmethod
    def _get_target_field_ids(
        items: Sequence[PatternItem],
    ) -> tuple[int | None, ...]:
        return tuple(
            dict.fromkeys(
                item.target_field_id
                for item in items
                if (
                    item.item_kind == ItemKind.TARGET_FIELD
                    and item.target_field_id is not None
                )
            )
        )

    @staticmethod
    def _validate_pattern_items(
        *,
        pattern_id: int,
        items: Sequence[PatternItem],
    ) -> None:
        for item in items:
            if item.pattern_id != pattern_id:
                raise InvalidPatternError(
                    f"Pattern item {item.id} belongs to pattern "
                    f"{item.pattern_id}, not {pattern_id}."
                )

    @staticmethod
    def _require_pattern_id(
        pattern: GeneralizedPattern,
    ) -> int:
        if pattern.id is None:
            raise InvalidPatternError(
                "GeneralizedPattern must be persisted before matching."
            )

        return pattern.id

    @staticmethod
    def _require_pattern_position(
        item: PatternItem,
    ) -> int:
        if item.position is None:
            raise InvalidPatternError(
                f"Sequential pattern item {item.id} has no position."
            )

        return item.position

    @staticmethod
    def _calculate_confidence(
        *,
        pattern: GeneralizedPattern,
        matched_items: Sequence[MatchedPatternItem],
    ) -> float:
        evidence_confidence = sum(
            item.confidence
            for item in matched_items
        ) / len(matched_items)

        pattern_confidence = (
            pattern.confidence
            if pattern.confidence is not None
            else 1.0
        )

        return min(
            1.0,
            max(0.0, evidence_confidence * pattern_confidence),
        )