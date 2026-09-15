"""Snapshot execution boundary. Adapters read stored bytes, never create sources."""

from dataclasses import dataclass
from typing import Protocol

from extraction.schemas.capture import CaptureRequest
from extraction.schemas.evidence import FieldSelector, SourceScope
from sources.schemas.models import SourceFieldTracking, SourceSnapshot


@dataclass(frozen=True)
class ExtractionDefinitions:
    scopes: list[SourceScope]
    selectors: list[FieldSelector]
    fields: list[SourceFieldTracking]


class SnapshotExtractor(Protocol):
    async def extract(
        self, snapshot: SourceSnapshot, definitions: ExtractionDefinitions, *, capture_key: str
    ) -> CaptureRequest:
        """Return the same capture graph used by manual discovery.

        Use AUTOMATIC discovery, confirmed_by_human=False, and issues for missing
        or ambiguous values. Do not infer identities from row positions. Snapshot
        bytes come from acquisition's StoredFile, not a live URL fetch.
        """
        ...
