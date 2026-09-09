from typing import Mapping

from dataclass import dataclass, field


@dataclass(frozen=True, slots=True)
class SheetIntakeContract:
    required_headers: frozenset[str]
    optional_headers: frozenset[str]

    # Pola, które nie mogą być puste w konkretnym rekordzie.
    required_values: frozenset[str] = frozenset()

    # Alternatywne nazwy kolumn używane przez człowieka.
    header_aliases: Mapping[str, str] = field(
        default_factory=dict
    )

    allow_unknown_headers: bool = False

    @property
    def allowed_headers(self) -> frozenset[str]:
        return (
                self.required_headers
                | self.optional_headers
        )
