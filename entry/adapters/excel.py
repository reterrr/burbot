from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from entry.adapters.common import (
    RawBatch,
    RawRecord,
    WorkbookReader,
    WorkbookSheet,
)


DEFAULT_SHEET_NAMES: dict[WorkbookSheet, str] = {
    WorkbookSheet.METADATA: "metadata",
    WorkbookSheet.OPERATORS: "operators",
    WorkbookSheet.PROJECTS: "projects",
    WorkbookSheet.SOURCES: "sources",
    WorkbookSheet.PROJECT_OPERATORS: "project_operators",
    WorkbookSheet.PROJECT_GEOGRAPHIES: "project_geographies",
    WorkbookSheet.PROJECT_SOURCES: "project_sources",
    WorkbookSheet.SOURCE_SECTIONS: "source_sections",
    WorkbookSheet.SOURCE_SELECTORS: "source_selectors",
    WorkbookSheet.SOURCE_EXPECTATIONS: "source_expectations",
}


class WorkbookFormatError(ValueError):
    pass


class ExcelWorkbookReader(WorkbookReader):
    def __init__(
        self,
        sheet_names: Mapping[WorkbookSheet, str] | None = None,
    ) -> None:
        self._sheet_names = dict(
            sheet_names or DEFAULT_SHEET_NAMES
        )

    def iter_batches(
        self,
        path: Path,
        *,
        batch_size: int = 500,
    ) -> Iterator[RawBatch]:
        if batch_size <= 0:
            raise ValueError("batch_size musi być większy od zera")

        if not path.is_file():
            raise FileNotFoundError(
                f"Nie znaleziono pliku: {path}"
            )

        workbook = load_workbook(
            filename=path,
            read_only=True,
            data_only=True,
        )

        try:
            self._validate_required_sheets(workbook.sheetnames)

            for sheet in WorkbookSheet:
                excel_sheet_name = self._sheet_names[sheet]
                worksheet = workbook[excel_sheet_name]

                yield from self._iter_sheet_batches(
                    worksheet=worksheet,
                    sheet=sheet,
                    batch_size=batch_size,
                )
        finally:
            workbook.close()

    def _iter_sheet_batches(
        self,
        *,
        worksheet: Any,
        sheet: WorkbookSheet,
        batch_size: int,
    ) -> Iterator[RawBatch]:
        rows = worksheet.iter_rows(values_only=True)

        try:
            raw_headers = next(rows)
        except StopIteration:
            return

        headers = self._parse_headers(
            raw_headers=raw_headers,
            sheet_name=worksheet.title,
        )

        records: list[RawRecord] = []
        batch_number = 1

        # Pierwszy wiersz zawiera nagłówki, dlatego dane zaczynają się od 2.
        for row_number, values in enumerate(rows, start=2):
            if self._is_empty_row(values):
                continue

            row_data = self._build_row(
                headers=headers,
                values=values,
                sheet_name=worksheet.title,
                row_number=row_number,
            )

            records.append(
                RawRecord(
                    row_number=row_number,
                    data=row_data,
                )
            )

            if len(records) >= batch_size:
                yield RawBatch(
                    sheet=sheet,
                    batch_number=batch_number,
                    records=tuple(records),
                )

                records.clear()
                batch_number += 1

        if records:
            yield RawBatch(
                sheet=sheet,
                batch_number=batch_number,
                records=tuple(records),
            )

    def _validate_required_sheets(
        self,
        available_sheets: list[str],
    ) -> None:
        missing_sheets = [
            excel_name
            for excel_name in self._sheet_names.values()
            if excel_name not in available_sheets
        ]

        if missing_sheets:
            raise WorkbookFormatError(
                "Brak wymaganych arkuszy: "
                f"{', '.join(sorted(missing_sheets))}"
            )

    @staticmethod
    def _parse_headers(
        *,
        raw_headers: tuple[Any, ...],
        sheet_name: str,
    ) -> tuple[str, ...]:
        headers: list[str] = []

        for column_number, value in enumerate(
            raw_headers,
            start=1,
        ):
            if value is None:
                raise WorkbookFormatError(
                    f"Brak nagłówka w arkuszu "
                    f"'{sheet_name}', kolumna {column_number}"
                )

            header = str(value).strip()

            if not header:
                raise WorkbookFormatError(
                    f"Pusty nagłówek w arkuszu "
                    f"'{sheet_name}', kolumna {column_number}"
                )

            headers.append(header)

        duplicates = {
            header
            for header in headers
            if headers.count(header) > 1
        }

        if duplicates:
            raise WorkbookFormatError(
                f"Powtórzone nagłówki w arkuszu "
                f"'{sheet_name}': {sorted(duplicates)}"
            )

        return tuple(headers)

    @staticmethod
    def _build_row(
        *,
        headers: tuple[str, ...],
        values: tuple[Any, ...],
        sheet_name: str,
        row_number: int,
    ) -> dict[str, Any]:
        additional_values = values[len(headers):]

        if any(value is not None for value in additional_values):
            raise WorkbookFormatError(
                f"Wiersz {row_number} arkusza '{sheet_name}' "
                "zawiera dane poza zdefiniowanymi kolumnami"
            )

        return {
            header: values[index] if index < len(values) else None
            for index, header in enumerate(headers)
        }

    @staticmethod
    def _is_empty_row(values: tuple[Any, ...]) -> bool:
        return all(
            value is None
            or (
                isinstance(value, str)
                and not value.strip()
            )
            for value in values
        )