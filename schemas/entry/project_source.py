"""Input schema linking BUR projects to monitored sources."""

# schemas/entry/project_source.py

from pydantic import Field

from mapping_status import MappingStatus
from source_type import SourceType
from common import BurInputModel, ExternalRef


class BurProjectSourceIn(BurInputModel):
    """Validate an association between a BUR project and sources.

    :ivar project_source_ref: Stable external reference to the project sources.
    :ivar project_ref: Stable external reference to the project.
    :ivar source_ref: Stable external reference to the sources.
    :ivar source_type: Source type.
    :ivar mapping_status: Mapping status.
    :ivar monitoring_enabled: Whether monitoring enabled.
    :ivar requires_manual_review: Requires manual review.
    :ivar priority: Priority.
    :ivar check_interval_minutes: Check interval minutes.
    :ivar notes: Optional notes supplied by an operator or importer.
    """
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
