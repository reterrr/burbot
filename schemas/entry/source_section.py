"""Input schemas for logical sections of BUR sources."""

# schemas/entry/source_section.py

from enum import StrEnum

from mapping_status import MappingStatus
from common import BurInputModel, ExternalRef


class SourceSectionType(StrEnum):
    """Enumerate the supported sources section type values."""
    SINGLE_CONTENT = "single_content"
    ITEM_LIST = "item_list"
    DOCUMENT_LIST = "document_list"
    TABLE = "table"
    PAGINATED_LIST = "paginated_list"
    ARCHIVE = "archive"
    OTHER = "other"


class BurSourceSectionIn(BurInputModel):
    """Validate one logical section of a BUR sources.

    :ivar section_ref: Stable external reference to the section.
    :ivar project_source_ref: Stable external reference to the project sources.
    :ivar name: Human-readable name.
    :ivar section_type: Section type.
    :ivar mapping_status: Mapping status.
    :ivar enabled: Enabled.
    :ivar notes: Optional notes supplied by an operator or importer.
    """
    section_ref: ExternalRef
    project_source_ref: ExternalRef

    name: str
    section_type: SourceSectionType

    mapping_status: MappingStatus = MappingStatus.REQUIRES_ANALYSIS
    enabled: bool = True

    notes: str | None = None
