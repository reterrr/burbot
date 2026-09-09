from typing import Any

from entry.adapters.common import WorkbookSheet


class IntakeValidationError(ValueError):
    """
    Bazowy kontrolowany wyjątek danych wejściowych.
    """

    code = "INTAKE_VALIDATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.details = details or {}


class InvalidSheetHeadersError(IntakeValidationError):
    code = "INVALID_SHEET_HEADERS"

    def __init__(
        self,
        *,
        sheet: WorkbookSheet,
        missing_headers: set[str],
        unexpected_headers: set[str],
    ) -> None:
        super().__init__(
            f"Nieprawidłowa struktura arkusza '{sheet.value}'",
            details={
                "sheet": sheet.value,
                "missing_headers": sorted(missing_headers),
                "unexpected_headers": sorted(
                    unexpected_headers
                ),
            },
        )


class DuplicateCanonicalHeaderError(
    IntakeValidationError
):
    code = "DUPLICATE_CANONICAL_HEADER"

    def __init__(
        self,
        *,
        sheet: WorkbookSheet,
        canonical_header: str,
    ) -> None:
        super().__init__(
            (
                f"Kilka kolumn arkusza '{sheet.value}' "
                f"wskazuje na pole '{canonical_header}'"
            ),
            details={
                "sheet": sheet.value,
                "canonical_header": canonical_header,
            },
        )


class MissingRequiredValueError(
    IntakeValidationError
):
    code = "MISSING_REQUIRED_VALUE"

    def __init__(
        self,
        *,
        sheet: WorkbookSheet,
        batch_number: int,
        row_number: int,
        field_name: str,
    ) -> None:
        super().__init__(
            (
                f"Brak wymaganej wartości '{field_name}' "
                f"w arkuszu '{sheet.value}', "
                f"wiersz {row_number}"
            ),
            details={
                "sheet": sheet.value,
                "batch_number": batch_number,
                "row_number": row_number,
                "field_name": field_name,
            },
        )