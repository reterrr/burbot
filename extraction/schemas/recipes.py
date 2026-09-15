"""Reusable WHERE + HOW contracts shared by capture and snapshot adapters."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from extraction.schemas.api import NonBlank, RequestModel
from extraction.schemas.enums import DiscoveryMethod, SelectorType

Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
SupportedExtractionAttribute = Literal["href", "src", "datetime", "title", "alt", "content"]


class TextExtraction(RequestModel):
    type: Literal["text"] = "text"


class AttributeExtraction(RequestModel):
    type: Literal["attribute"] = "attribute"
    attribute: SupportedExtractionAttribute


class SelectionQuote(RequestModel):
    # Whitespace is part of the anchor, especially at the edges of prefix/suffix.
    exact: str = Field(min_length=1)
    prefix: str
    suffix: str


class SelectionExtraction(RequestModel):
    type: Literal["selection"] = "selection"
    quote: SelectionQuote


class PageUrlExtraction(RequestModel):
    type: Literal["pageUrl"] = "pageUrl"


ExtractionSpec = Annotated[
    TextExtraction | AttributeExtraction | SelectionExtraction | PageUrlExtraction,
    Field(discriminator="type"),
]


class LocatorRequest(RequestModel):
    type: SelectorType
    value: NonBlank


class SelectorRequest(LocatorRequest):
    """A scope locator and its discovery annotations; no field extraction operation."""

    confidence: Confidence = 1.0
    discovered_by: DiscoveryMethod = DiscoveryMethod.MANUAL


class FieldExtractionRuleRequest(RequestModel):
    selector: LocatorRequest | None = None
    extraction: ExtractionSpec
    confidence: Confidence = 1.0
    discovered_by: DiscoveryMethod = DiscoveryMethod.MANUAL

    @model_validator(mode="after")
    def locator_for_operation(self) -> Self:
        if self.extraction.type == "pageUrl":
            if self.selector is not None:
                raise ValueError("pageUrl extraction must not have a selector")
        elif self.selector is None:
            raise ValueError("Element extraction requires a selector")
        return self
