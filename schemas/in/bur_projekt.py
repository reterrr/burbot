from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from geography.general import Wojewodztwo, Podregion, Gmina
from mapping_status import MappingStatus
from source_content_type import SourceContentType
from source_type import SourceType

import geography.general


class ProjectStatus(StrEnum):
    REQUIRES_MAPPING = "requires_mapping"
    MAPPING_IN_PROGRESS = "mapping_in_progress"
    READY_FOR_IMPORT = "ready_for_import"
    MANUAL_ONLY = "manual_only"
    INACTIVE = "inactive"


@dataclass(slots=True)
class BurProjectIn:
    id: int
    name: str
    status: ProjectStatus = ProjectStatus.REQUIRES_MAPPING
    wojewodztwa: list[Wojewodztwo] | None = None
    podregiony: list[Podregion] | None = None
    powiaty: list[Powiat] | None = None
    gminy: list[Gmina] | None = None


@dataclass(slots=True)
class BurSourceIn:
    project_id: int
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

@dataclass(slots=True)
class BurOperatorIn:
    id: int
    nip: int
    name: str
    url: str


@dataclass(slots=True)
class BurProjectOperator:
    project_id: int
    operator_id: int