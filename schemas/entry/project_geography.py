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
    INCLUDE = "include"
    EXCLUDE = "exclude"


class BurProjectGeographyIn(BurInputModel):
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
