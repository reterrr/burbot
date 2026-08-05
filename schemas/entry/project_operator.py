"""Input schemas for assigning operators to BUR projects."""

# schemas/entry/project_operator.py

from datetime import date
from enum import StrEnum

from pydantic import model_validator

from common import BurInputModel, ExternalRef


class ProjectOperatorRole(StrEnum):
    """Enumerate the supported project operator role values."""
    PRIMARY_OPERATOR = "primary_operator"
    CO_OPERATOR = "co_operator"
    PARTNER = "partner"
    TECHNICAL_PARTNER = "technical_partner"


class BurProjectOperatorIn(BurInputModel):
    """Validate one operator assignment for a BUR project.

    :ivar project_operator_ref: Stable external reference to the project operator.
    :ivar project_ref: Stable external reference to the project.
    :ivar operator_ref: Stable external reference to the operator.
    :ivar role: Role.
    :ivar valid_from: Timestamp from which this version is valid.
    :ivar valid_to: Timestamp until which this version is valid, if closed.
    :ivar notes: Optional notes supplied by an operator or importer.
    """
    project_operator_ref: ExternalRef

    project_ref: ExternalRef
    operator_ref: ExternalRef

    role: ProjectOperatorRole

    valid_from: date | None = None
    valid_to: date | None = None

    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "BurProjectOperatorIn":
        """Validate that the assignment date range is chronological.

        :raises ValueError: If the supplied data violates schema constraints.
        :return: Validated model instance.
        """
        if (
                self.valid_from is not None
                and self.valid_to is not None
                and self.valid_to < self.valid_from
        ):
            raise ValueError(
                "valid_to nie może być wcześniejsze niż valid_from"
            )

        return self
