from bs4 import Tag

from db import PatternItem
from services.extraction.evidence import EvidenceBuilder, EvidenceToken
from services.extraction.matchers.pattern_matching_protocol import (PatternMatchingProtocol,
                                                                    PatternDefinition,
                                                                    NodeMatchResults, PatternOccurrence,
                                                                    PartialPatternOccurrence, MatchResult)


class UnorderedPatternMatchingProtocol(PatternMatchingProtocol):
    def __init__(
            self,
            evidence_builder: EvidenceBuilder
    ) -> None:
        self._evidence_builder = evidence_builder

    async def match(
            self,
            node: Tag,
            pattern: PatternDefinition,
    ) -> NodeMatchResults:
        results = NodeMatchResults()
        items = pattern.pattern_items

        text = node.get_text(" ", strip=True)

        evidences = await self._evidence_builder.build(text)

        for end in range(len(evidences), len(items) - 1, -1):
            window_evidence = evidences[end - len(items):end]
            match = UnorderedPatternMatchingProtocol._match(items, window_evidence)

            if isinstance(match, PatternOccurrence):
                results.done.setdefault(pattern.pattern, []).append(match)
            else:
                results.partial.setdefault(pattern.pattern, []).append(match)

        return results

    @staticmethod
    def _match(
            items: list[PatternItem],
            evidences: list[EvidenceToken],
    ) -> PatternOccurrence | PartialPatternOccurrence:

        candidates: list[list[int]] = []

        for item in items:
            candidates.append([
                index
                for index, evidence in enumerate(evidences)
                if any(
                    clas.id == item.token_class_id
                    for clas in evidence.classes
                )
            ])

        evidence_owner: dict[int, int] = {}

        def assign(
                item_index: int,
                visited: set[int],
        ) -> bool:
            for evidence_index in candidates[item_index]:
                if evidence_index in visited:
                    continue

                visited.add(evidence_index)

                current_owner = evidence_owner.get(evidence_index)

                if (
                        current_owner is None
                        or assign(current_owner, visited)
                ):
                    evidence_owner[evidence_index] = item_index
                    return True

            return False

        order = sorted(
            range(len(items)),
            key=lambda i: len(candidates[i]),
        )

        for item_index in order:
            assign(item_index, set())

        item_to_evidence = {
            item_index: evidence_index
            for evidence_index, item_index in evidence_owner.items()
        }

        results = [
            MatchResult(
                pattern_item=items[item_index],
                evidence=evidences[evidence_index],
            )
            for item_index, evidence_index in item_to_evidence.items()
        ]

        if len(results) == len(items):
            return PatternOccurrence(results)

        missing = [
            item
            for index, item in enumerate(items)
            if index not in item_to_evidence
        ]

        return PartialPatternOccurrence(
            results,
            missing,
        )
