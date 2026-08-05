"""Input schema and validation for BUR operators."""

# schemas/entry/operator.py

import re

from pydantic import AnyHttpUrl, field_validator

from common import BurInputModel, ExternalRef

class BurOperatorIn(BurInputModel):
    """Validate an operator supplied by a BUR import.

    :ivar operator_ref: Stable external reference to the operator.
    :ivar name: Human-readable name.
    :ivar nip: Normalized ten-digit Polish tax identifier.
    :ivar website_url: Optional public website URL.
    :ivar active: Active.
    :ivar notes: Optional notes supplied by an operator or importer.
    """
    operator_ref: ExternalRef

    name: str
    nip: str

    website_url: AnyHttpUrl | None = None
    active: bool = True
    notes: str | None = None

    @field_validator("nip", mode="before")
    @classmethod
    def normalize_and_validate_nip(cls, value: object) -> str:
        """Normalize a Polish NIP and validate its checksum.

        :param value: Raw value to normalize and validate.
        :raises ValueError: If the supplied data violates schema constraints.
        :return: Normalized ten-digit NIP.
        """
        if value is None:
            raise ValueError("NIP jest wymagany")

        nip = re.sub(r"[^0-9]", "", str(value))

        if len(nip) != 10:
            raise ValueError("NIP musi zawierać dokładnie 10 cyfr")

        weights = (6, 5, 7, 2, 3, 4, 5, 6, 7)
        checksum = sum(
            int(digit) * weight
            for digit, weight in zip(nip[:9], weights, strict=True)
        ) % 11

        if checksum == 10 or checksum != int(nip[-1]):
            raise ValueError(f"Nieprawidłowa suma kontrolna NIP: {nip}")

        return nip
