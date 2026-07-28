from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from mapping_status import MappingStatus
from source_content_type import SourceContentType
from source_type import SourceType


class ProjectStatus(StrEnum):
    REQUIRES_MAPPING = "requires_mapping"
    MAPPING_IN_PROGRESS = "mapping_in_progress"
    READY_FOR_IMPORT = "ready_for_import"
    MANUAL_ONLY = "manual_only"
    INACTIVE = "inactive"


@dataclass(slots=True)
class BurSourceIn:
    project_ref: str

    name: str
    url: str
    source_type: SourceType

    content_type: SourceContentType = SourceContentType.UNKNOWN
    mapping_status: MappingStatus = MappingStatus.REQUIRES_ANALYSIS

    active: bool = True
    requires_javascript: bool = False
    requires_manual_review: bool = False

    content_selector: str | None = None
    links_selector: str | None = None
    ignored_selectors: list[str] = field(default_factory=list)

    expected_information: list[str] = field(default_factory=list)

    last_verified_at: date | None = None
    notes: str | None = None
