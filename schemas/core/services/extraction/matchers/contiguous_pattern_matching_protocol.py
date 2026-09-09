from bs4 import Tag

from db import PatternItem
from db.enums import ItemsetRole
from services.extraction.evidence import EvidenceBuilder, EvidenceToken
from services.extraction.matchers.pattern_matching_protocol import (
    PatternMatchingProtocol,
    PatternDefinition,
    NodeMatchResults,
    MatchResult, PatternOccurrence, PartialPatternOccurrence
)


class ContiguousMatcher(PatternMatchingProtocol):
    def __init__(
            self,
            evidence_builder: EvidenceBuilder,
            must: list[ItemsetRole],
    ) -> None:
        self._evidence_builder = evidence_builder
        self._must = must

    # optimize window sliding
    async def match(
            self,
            node: Tag,
            pattern: PatternDefinition,
    ) -> NodeMatchResults:
        items = pattern.pattern_items
        results = NodeMatchResults()

        if not items:
            return results

        text = node.get_text(" ", strip=True)
        evidences = await self._evidence_builder.build(text)

        pattern_length = len(items)

        for start in range(len(evidences) - pattern_length + 1):
            window = evidences[start:start + pattern_length]

            if len(evidences) < pattern_length:
                return results

            if self._all_matches_window(items, window):
                matches = [
                    MatchResult(
                        pattern_item=item,
                        evidence=token,
                    )
                    for item, token in zip(items, window)
                ]

                results.done.setdefault(
                    pattern.pattern,
                    []
                ).append(PatternOccurrence(matches=matches))
            else:
                partials = self._partial_matches_window(items, window, self._must)

                if not partials:
                    continue

                missing = items.copy()

                for partial in partials:
                    missing.remove(partial.pattern_item)

                results.partial.setdefault(
                    pattern.pattern,
                    []
                ).append(PartialPatternOccurrence(matches=partials, missing_items=missing))

        return results

    @staticmethod
    def _all_matches_window(
            items: list[PatternItem],
            evidence: list[EvidenceToken],
    ) -> bool:
        return all(
            ContiguousMatcher._matches(pattern_item, evidence_token)
            for pattern_item, evidence_token
            in zip(items, evidence)
        )

    @staticmethod
    def _any_matches_window(
            items: list[PatternItem],
            evidence: list[EvidenceToken],
    ) -> bool:
        return any(
            ContiguousMatcher._matches(pattern_item, evidence_token)
            for pattern_item, evidence_token
            in zip(items, evidence)
        )

    @staticmethod
    def _partial_matches_window(
            items: list[PatternItem],
            evidences: list[EvidenceToken],
            must: list[ItemsetRole],
    ) -> list[MatchResult]:

        if not must:
            return []

        for start in range(len(items) - len(must) + 1):
            item_window = items[start:start + len(must)]
            evidence_window = evidences[start:start + len(must)]

            roles_match = all(
                item.role == required_role
                for item, required_role
                in zip(item_window, must)
            )

            if not roles_match:
                continue

            matches = [
                MatchResult(
                    pattern_item=item,
                    evidence=evidence,
                )
                for item, evidence
                in zip(item_window, evidence_window)
                if ContiguousMatcher._matches(item, evidence)
            ]

            if len(matches) == len(must):
                return matches

        return []

    @staticmethod
    def _matches(
            pattern_item: PatternItem,
            evidence: EvidenceToken,
    ) -> bool:
        return any(
            token_class.id == pattern_item.token_class_id
            for token_class
            in evidence.classes
        )
