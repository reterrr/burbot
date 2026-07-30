from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

RawRow = dict[str, Any]

@dataclass(frozen=True, slots=True)
class RawWorkbook:
    metadata: list[RawRow]
    operators: list[RawRow]
    projects: list[RawRow]
    project_operators: list[RawRow]
    project_geographies: list[RawRow]
    sources: list[RawRow]
    project_sources: list[RawRow]
    source_sections: list[RawRow]
    source_selectors: list[RawRow]
    source_expectations: list[RawRow]


class WorkbookReader(Protocol):
    def read(self, path: Path) -> RawWorkbook:
        ...
