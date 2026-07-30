from enum import StrEnum
from pathlib import Path

from entry.adapters.common import WorkbookReader, RawWorkbook


class ImportOperationType(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    DISABLE = "disable"
    CONFLICT = "conflict"

class ExcelWorkBookReader(WorkbookReader):
    def read(self, path: Path) -> RawWorkbook:




