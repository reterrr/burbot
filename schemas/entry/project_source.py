# schemas/entry/project_source.py

from pydantic import Field

from mapping_status import MappingStatus
from source_type import SourceType
from common import BurInputModel, ExternalRef


class BurProjectSourceIn(BurInputModel):
    project_source_ref: ExternalRef

    project_ref: ExternalRef
    source_ref: ExternalRef

    source_type: SourceType
    mapping_status: MappingStatus = MappingStatus.REQUIRES_ANALYSIS

    monitoring_enabled: bool = True
    requires_manual_review: bool = False

    priority: int = Field(default=50, ge=0, le=100)

    check_interval_minutes: int | None = Field(
        default=None,
        ge=5,
    )

    notes: str | None = None