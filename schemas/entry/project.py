"""Input schema and validation for BUR projects."""

# schemas/entry/project.py

from datetime import date, datetime

from pydantic import AnyHttpUrl, model_validator

from enums.project_status import (
    ProjectLifecycleStatus,
    ProjectOnboardingStatus,
)
from common import BurInputModel, ExternalRef


class BurProjectIn(BurInputModel):
    """Validate a project supplied by a BUR import.

    :ivar project_ref: Stable external reference to the project.
    :ivar name: Human-readable name.
    :ivar main_url: Primary URL of the project.
    :ivar onboarding_status: Onboarding status.
    :ivar lifecycle_status: Lifecycle status.
    :ivar monitoring_enabled: Whether monitoring enabled.
    :ivar starts_at: Timestamp for starts.
    :ivar ends_at: Timestamp for ends.
    :ivar last_verified_at: Timestamp for last verified.
    :ivar notes: Optional notes supplied by an operator or importer.
    """
    project_ref: ExternalRef

    name: str
    main_url: AnyHttpUrl

    onboarding_status: ProjectOnboardingStatus = (
        ProjectOnboardingStatus.REQUIRES_MAPPING
    )
    lifecycle_status: ProjectLifecycleStatus = (
        ProjectLifecycleStatus.ACTIVE
    )

    monitoring_enabled: bool = True

    starts_at: date | None = None
    ends_at: date | None = None

    last_verified_at: datetime | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_project_dates(self) -> "BurProjectIn":
        """Validate that the project date range is chronological.

        :raises ValueError: If the supplied data violates schema constraints.
        :return: Validated model instance.
        """
        if (
                self.starts_at is not None
                and self.ends_at is not None
                and self.ends_at < self.starts_at
        ):
            raise ValueError(
                "Data zakończenia projektu nie może być "
                "wcześniejsza niż data rozpoczęcia"
            )

        return self
