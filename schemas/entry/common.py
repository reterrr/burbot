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
    """
    Bazowy model wszystkich danych wejściowych.

    extra="forbid":
        literówka w nazwie kolumny nie zostanie cicho zignorowana.

    frozen=True:
        dane po walidacji są niezmienne.

    str_strip_whitespace=True:
        usuwa przypadkowe spacje z Excela.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )
