# schemas/entry/source_selector.py

from enum import StrEnum

from pydantic import Field

from common import BurInputModel, ExternalRef


class SelectorLanguage(StrEnum):
    CSS = "css"
    XPATH = "xpath"
    JSON_PATH = "json_path"
    REGEX = "regex"


class SelectorPurpose(StrEnum):
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