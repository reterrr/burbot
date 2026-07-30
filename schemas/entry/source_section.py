# schemas/entry/source_section.py

from enum import StrEnum

from mapping_status import MappingStatus
from common import BurInputModel, ExternalRef


class SourceSectionType(StrEnum):
    SINGLE_CONTENT = "single_content"
    ITEM_LIST = "item_list"
    DOCUMENT_LIST = "document_list"
    TABLE = "table"
    PAGINATED_LIST = "paginated_list"
    ARCHIVE = "archive"
    OTHER = "other"


class BurSourceSectionIn(BurInputModel):
    section_ref: ExternalRef
    project_source_ref: ExternalRef

    name: str
    section_type: SourceSectionType

    mapping_status: MappingStatus = MappingStatus.REQUIRES_ANALYSIS
    enabled: bool = True

    notes: str | None = None
