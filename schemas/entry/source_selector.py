"""Input schemas for selectors applied to BUR sources sections."""

# schemas/entry/source_selector.py

from enum import StrEnum

from pydantic import Field

from common import BurInputModel, ExternalRef


class SelectorLanguage(StrEnum):
    """Enumerate the supported selector language values."""
    CSS = "css"
    XPATH = "xpath"
    JSON_PATH = "json_path"
    REGEX = "regex"


class SelectorPurpose(StrEnum):
    """Enumerate the supported selector purpose values."""
    CONTAINER = "container"
    ITEM = "item"
    TITLE = "title"
    LINK = "link"
    DATE = "date"
    BODY = "body"
    STATUS = "status"
    DOCUMENT = "document"
    NEXT_PAGE = "next_page"
    IGNORE = "ignore"


class BurSourceSelectorIn(BurInputModel):
    """Validate one selector attached to a BUR sources section.

    :ivar selector_ref: Stable external reference to the selector.
    :ivar section_ref: Stable external reference to the section.
    :ivar purpose: Purpose.
    :ivar language: Language.
    :ivar expression: Expression.
    :ivar attribute_name: Attribute name.
    :ivar returns_many: Returns many.
    :ivar required: Required.
    :ivar order: Order.
    :ivar notes: Optional notes supplied by an operator or importer.
    """
    selector_ref: ExternalRef
    section_ref: ExternalRef

    purpose: SelectorPurpose
    language: SelectorLanguage = SelectorLanguage.CSS

    expression: str

    attribute_name: str | None = None
    returns_many: bool = False
    required: bool = True

    order: int = Field(default=0, ge=0)

    notes: str | None = None
