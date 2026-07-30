# schemas/entry/project_operator.py

from datetime import date
from enum import StrEnum

from pydantic import model_validator

from common import BurInputModel, ExternalRef


class ProjectOperatorRole(StrEnum):
    PRIMARY_OPERATOR = "primary_operator"
    CO_OPERATOR = "co_operator"
    PARTNER = "partner"
    TECHNICAL_PARTNER = "technical_partner"


class BurProjectOperatorIn(BurInputModel):
    project_operator_ref: ExternalRef

    project_ref: ExternalRef
    operator_ref: ExternalRef

    role: ProjectOperatorRole

    valid_from: date | None = None
    valid_to: date | None = None

    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "BurProjectOperatorIn":
        if (
                self.valid_from is not None
                and self.valid_to is not None
                and self.valid_to < self.valid_from
        ):
            raise ValueError(
                "valid_to nie może być wcześniejsze niż valid_from"
            )

        return self
