from dataclasses import dataclass, field
from typing import Protocol

from bs4 import Tag

from db import PatternItem
from services.extraction.evidence import EvidenceToken


@dataclass
class PatternDefinition:
    pattern: int
    pattern_items: list[PatternItem]


@dataclass
class MatchResult:
    pattern_item: PatternItem
    evidence: EvidenceToken


@dataclass
class PatternOccurrence:
    matches: list[MatchResult]

    @property
    def matched_count(self) -> int:
        return len(self.matches)


@dataclass
class PartialPatternOccurrence:
    matches: list[MatchResult]
    missing_items: list[PatternItem]

    @property
    def matched_count(self) -> int:
        return len(self.matches)

    @property
    def completeness(self) -> float:
        total = len(self.matches) + len(self.missing_items)

        if total == 0:
            return 0.0

        return len(self.matches) / total


@dataclass
class NodeMatchResults:
    done: dict[int, list[PatternOccurrence]] = field(default_factory=dict)
    partial: dict[int, list[PartialPatternOccurrence]] = field(default_factory=dict)


class PatternMatchingProtocol(Protocol):
    async def match(
            self,
            node: Tag,
            pattern: PatternDefinition,
    ) -> NodeMatchResults:
        """Match ordered pattern items against candidate DOM nodes."""
        ...
