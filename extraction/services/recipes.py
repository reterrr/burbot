"""Validate persisted recipes and read literals from an already located HTML node.

Locating/parsing snapshot nodes remains the SnapshotExtractor adapter's job.
These operations never fetch a URL, resolve relative attributes, or normalize text.
"""

from dataclasses import dataclass

from pydantic import ValidationError

from extraction.exceptions import ExtractionConflict, ExtractionValidationError
from extraction.schemas.enums import ExtractionIssueCode
from extraction.schemas.evidence import FieldSelector
from extraction.schemas.recipes import ExtractionSpec, FieldExtractionRuleRequest


def stored_rule(row: FieldSelector) -> FieldExtractionRuleRequest:
    if row.extraction_json is None:
        raise ExtractionConflict(
            f"Field recipe {row.id} has no extraction spec; manual rediscovery is required"
        )
    selector = None
    if row.selector_type is not None or row.selector_string is not None:
        selector = {"type": row.selector_type, "value": row.selector_string}
    try:
        return FieldExtractionRuleRequest.model_validate(
            {
                "selector": selector,
                "extraction": row.extraction_json,
                "confidence": row.confidence_score,
                "discovered_by": row.discovered_by,
            }
        )
    except ValidationError as error:
        raise ExtractionValidationError(
            f"Invalid stored field recipe {row.id}; manual rediscovery is required"
        ) from error


@dataclass(frozen=True)
class ReadLiteral:
    raw_value: str
    char_start: int | None = None
    char_end: int | None = None


class RecipeReadError(Exception):
    """An adapter can translate this into an IssueRequest for the field/occurrence."""

    def __init__(self, code: ExtractionIssueCode, message: str):
        super().__init__(message)
        self.code = code


def read_html_literal(
    extraction: ExtractionSpec,
    *,
    text_content: str | None = None,
    attributes: dict[str, str] | None = None,
    page_url: str | None = None,
) -> ReadLiteral:
    """Read full node text, a raw attribute, a contextual quote, or snapshot URL.

    Text and selection offsets are half-open Unicode code-point ranges. An empty
    prefix/suffix imposes no context restriction. A quote must match uniquely;
    missing or ambiguous anchors never fall back to the full paragraph.
    """
    match extraction.type:
        case "text":
            value = text_content
            result = ReadLiteral(value, 0, len(value)) if value is not None else None
        case "attribute":
            value = (attributes or {}).get(extraction.attribute)
            result = ReadLiteral(value) if value is not None else None
        case "pageUrl":
            value = page_url
            result = ReadLiteral(value) if value is not None else None
        case "selection":
            content = text_content or ""
            quote = extraction.quote
            positions = []
            start = content.find(quote.exact)
            while start >= 0:
                end = start + len(quote.exact)
                if content.endswith(quote.prefix, 0, start) and content.startswith(
                    quote.suffix, end
                ):
                    positions.append(start)
                    if len(positions) > 1:
                        raise RecipeReadError(
                            ExtractionIssueCode.AMBIGUOUS_MATCH,
                            "Selection quote matches more than one position",
                        )
                start = content.find(quote.exact, start + 1)
            if not positions:
                raise RecipeReadError(
                    ExtractionIssueCode.VALUE_NOT_FOUND, "Selection quote was not found"
                )
            result = ReadLiteral(quote.exact, positions[0], positions[0] + len(quote.exact))
        case _:
            raise ValueError("Unsupported extraction operation")
    if result is None or not isinstance(result.raw_value, str) or not result.raw_value.strip():
        raise RecipeReadError(ExtractionIssueCode.VALUE_NOT_FOUND, "Extraction produced no literal")
    return result
