# enums/project_status.py

from enum import StrEnum


class ProjectOnboardingStatus(StrEnum):
    DISCOVERED = "discovered"
    REQUIRES_MAPPING = "requires_mapping"
    MAPPING_IN_PROGRESS = "mapping_in_progress"
    REQUIRES_VERIFICATION = "requires_verification"
    READY_FOR_IMPORT = "ready_for_import"
    MANUAL_ONLY = "manual_only"
    REJECTED = "rejected"


class ProjectLifecycleStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    TEMPORARILY_INACTIVE = "temporarily_inactive"
    COMPLETED = "completed"
    ARCHIVED = "archived"