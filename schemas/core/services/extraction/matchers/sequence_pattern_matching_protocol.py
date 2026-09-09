from bs4 import Tag

from db import PatternItem
from services.extraction.evidence import EvidenceBuilder, EvidenceToken
from services.extraction.matchers.pattern_matching_protocol import (
    PatternDefinition,
    PatternMatchingProtocol,
    NodeMatchResults,
    MatchResult,
    PatternOccurrence,
    PartialPatternOccurrence,
)


class SequentialMatcher(PatternMatchingProtocol):
    def __init__(
            self,
            evidence_builder: EvidenceBuilder,
    ) -> None:
        self._evidence_builder = evidence_builder

    async def match(
            self,
            node: Tag,
            pattern: PatternDefinition,
    ) -> NodeMatchResults:
        results = NodeMatchResults()

        if not pattern.pattern_items:
            return results

        text = node.get_text(" ", strip=True)
        evidence = await self._evidence_builder.build(text)

        position = 0

        while position < len(evidence):
            occurrence, next_position = self._match_sequence(
                evidence=evidence,
                items=pattern.pattern_items,
                start_position=position,
            )

            if occurrence is None:
                break

            if isinstance(occurrence, PatternOccurrence):
                results.done.setdefault(
                    pattern.pattern,
                    [],
                ).append(occurrence)

                position = next_position
                continue

            results.partial.setdefault(
                pattern.pattern,
                [],
            ).append(occurrence)

            # A partial occurrence reached the end of the evidence,
            # so there is nothing else to search.
            break

        return results

    def _match_sequence(
            self,
            evidence: list[EvidenceToken],
            items: list[PatternItem],
            start_position: int,
    ) -> tuple[
        PatternOccurrence | PartialPatternOccurrence | None,
        int,
    ]:
        matched: list[MatchResult] = []
        expected_index = 0

        for position in range(start_position, len(evidence)):
            token = evidence[position]
            expected = items[expected_index]

            if not self._matches(expected, token):
                continue

            matched.append(
                MatchResult(
                    pattern_item=expected,
                    evidence=token,
                )
            )

            expected_index += 1

            if expected_index == len(items):
                return (
                    PatternOccurrence(
                        matches=matched,
                    ),
                    position + 1,
                )

        if matched:
            return (
                PartialPatternOccurrence(
                    matches=matched,
                    missing_items=items[expected_index:],
                ),
                len(evidence),
            )

        return None, len(evidence)

    @staticmethod
    def _matches(
            pattern_item: PatternItem,
            evidence: EvidenceToken,
    ) -> bool:
        return any(
            evidence_class.id == pattern_item.token_class_id
            for evidence_class in evidence.classes
        )
