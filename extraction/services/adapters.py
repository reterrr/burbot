"""Snapshot execution boundary. Adapters read stored bytes, never create sources."""

from dataclasses import dataclass
from typing import Protocol

from extraction.schemas.capture import CaptureRequest
from extraction.schemas.evidence import FieldSelector, SourceScope
from extraction.schemas.recipes import FieldExtractionRuleRequest
from extraction.services.recipes import stored_rule
from sources.schemas.models import SourceFieldTracking, SourceSnapshot


@dataclass(frozen=True)
class FieldRecipeDefinition:
    id: int
    scope_id: int
    source_field_tracking_id: int
    business_entity_field_id: int
    version: int
    rule: FieldExtractionRuleRequest


@dataclass(frozen=True)
class ExtractionDefinitions:
    scopes: list[SourceScope]
    # Historical collection name; each item is now a complete, typed field recipe.
    selectors: list[FieldRecipeDefinition]
    fields: list[SourceFieldTracking]

    @classmethod
    def from_rows(
        cls,
        scopes: list[SourceScope],
        selectors: list[FieldSelector],
        fields: list[SourceFieldTracking],
    ) -> "ExtractionDefinitions":
        field_ids = {f.id: f.business_entity_field_id for f in fields}
        return cls(
            scopes=[SourceScope.model_validate(s.model_dump()) for s in scopes],
            selectors=[
                FieldRecipeDefinition(
                    id=s.id,
                    scope_id=s.scope_id,
                    source_field_tracking_id=s.source_field_tracking_id,
                    business_entity_field_id=field_ids[s.source_field_tracking_id],
                    version=s.version,
                    rule=stored_rule(s),
                )
                for s in selectors
            ],
            fields=[SourceFieldTracking.model_validate(f.model_dump()) for f in fields],
        )


class SnapshotExtractor(Protocol):
    async def extract(
        self, snapshot: SourceSnapshot, definitions: ExtractionDefinitions, *, capture_key: str
    ) -> CaptureRequest:
        """Return the same capture graph used by manual discovery.

        Use AUTOMATIC discovery, confirmed_by_human=False, and issues for missing
        or ambiguous values. Do not infer identities from row positions. Snapshot
        bytes come from acquisition's StoredFile, not a live URL fetch. Each
        definitions.selectors item carries a validated .rule with locator and
        extraction spec. pageUrl reads snapshot.page_url. Omit ValueRequest.rule
        in the result: only manual rediscovery may update field recipes.
        """
        ...
