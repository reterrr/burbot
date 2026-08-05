"""Shared Pydantic types and configuration for BUR import schemas."""

# schemas/entry/clear.py

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

ExternalRef = Annotated[
    str,
    Field(
        min_length=2,
        max_length=120,
        pattern=r"^[A-Z0-9][A-Z0-9_-]*$",
    ),
]


class BurInputModel(BaseModel):
    """Provide strict, immutable configuration shared by all BUR input schemas."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )
