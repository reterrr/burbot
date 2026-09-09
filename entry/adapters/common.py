from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, overload, Sequence

RawRow = dict[str, Any]


class WorkbookSheet(StrEnum):
    METADATA = "metadata"
    OPERATORS = "operators"
    PROJECTS = "projects"
    SOURCES = "sources"

    PROJECT_OPERATORS = "project_operators"
    PROJECT_GEOGRAPHIES = "project_geographies"
    PROJECT_SOURCES = "project_sources"

    SOURCE_SECTIONS = "source_sections"
    SOURCE_SELECTORS = "source_selectors"
    SOURCE_EXPECTATIONS = "source_expectations"


@dataclass(frozen=True, slots=True)
class RawRecord:
    """
    Jeden rekord odczytany ze źródła.

    Zachowujemy numer wiersza, żeby błędy walidacji można było
    przypisać do konkretnego miejsca w Excelu.
    """

    row_number: int
    data: RawRow


@dataclass(frozen=True, slots=True)
class RawBatch(Sequence[RawRecord]):
    sheet: WorkbookSheet
    batch_number: int
    records: tuple[RawRecord, ...]

    def __iter__(self) -> Iterator[RawRecord]:
        return iter(self.records)

    def __len__(self) -> int:
        return len(self.records)

    @overload
    def __getitem__(self, index: int) -> RawRecord:
        ...

    @overload
    def __getitem__(
            self,
            index: slice,
    ) -> tuple[RawRecord, ...]:
        ...

    def __getitem__(
            self,
            index: int | slice,
    ) -> RawRecord | tuple[RawRecord, ...]:
        return self.records[index]

    @property
    def size(self) -> int:
        return len(self)

    @property
    def first_row_number(self) -> int | None:
        if not self:
            return None

        return self[0].row_number

    @property
    def last_row_number(self) -> int | None:
        if not self:
            return None

        return self[-1].row_number


class WorkbookReader(Protocol):
    def iter_batches(
            self,
            path: Path,
            *,
            batch_size: int = 500,
    ) -> Iterator[RawBatch]:
        ...
