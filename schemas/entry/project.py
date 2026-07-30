# schemas/entry/project.py

from datetime import date, datetime

from pydantic import AnyHttpUrl, model_validator

from enums.project_status import (
    ProjectLifecycleStatus,
    ProjectOnboardingStatus,
)
from common import BurInputModel, ExternalRef


class BurProjectIn(BurInputModel):
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
