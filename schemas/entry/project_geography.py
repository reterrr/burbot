"""Input schemas for assigning geographic units to BUR projects."""

# schemas/entry/project_geography.py

from enum import StrEnum

from pydantic import AnyHttpUrl, model_validator

from common import BurInputModel, ExternalRef
from geography.general import (
    Gmina,
    Podregion,
    Powiat,
    Wojewodztwo,
)


class GeographyAssignmentMode(StrEnum):
    """Enumerate the supported geography assignment mode values."""
    INCLUDE = "include"
    EXCLUDE = "exclude"


class BurProjectGeographyIn(BurInputModel):
    """Validate one geographic assignment for a BUR project.

    :ivar geography_ref: Stable external reference to the geography.
    :ivar project_ref: Stable external reference to the project.
    :ivar mode: Mode.
    :ivar wojewodztwo: Wojewodztwo.
    :ivar podregion: Podregion.
    :ivar powiat: Powiat.
    :ivar gmina: Gmina.
    :ivar evidence_url: URL providing evidence information.
    :ivar notes: Optional notes supplied by an operator or importer.
    """
    geography_ref: ExternalRef
    project_ref: ExternalRef

    mode: GeographyAssignmentMode = GeographyAssignmentMode.INCLUDE

    wojewodztwo: Wojewodztwo | None = None
    podregion: Podregion | None = None
    powiat: Powiat | None = None
    gmina: Gmina | None = None

    evidence_url: AnyHttpUrl | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_exactly_one_unit(
            self,
    ) -> "BurProjectGeographyIn":
        """Validate that exactly one geographic unit is selected.

        :raises ValueError: If the supplied data violates schema constraints.
        :return: Validated model instance.
        """
        selected_units = [
            self.wojewodztwo,
            self.podregion,
            self.powiat,
            self.gmina,
        ]

        selected_count = sum(
            value is not None
            for value in selected_units
        )

        if selected_count != 1:
            raise ValueError(
                "Należy wskazać dokładnie jedną jednostkę: "
                "kraj, województwo, podregion, powiat albo gminę"
            )

        return self
