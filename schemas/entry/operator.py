# schemas/entry/operator.py

import re

from pydantic import AnyHttpUrl, field_validator

from common import BurInputModel, ExternalRef

class BurOperatorIn(BurInputModel):
    operator_ref: ExternalRef

    name: str
    nip: str

    website_url: AnyHttpUrl | None = None
    active: bool = True
    notes: str | None = None

    @field_validator("nip", mode="before")
    @classmethod
    def normalize_and_validate_nip(cls, value: object) -> str:
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
