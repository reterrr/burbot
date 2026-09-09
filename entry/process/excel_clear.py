import math
import re
import unicodedata
from typing import Iterator, Mapping, Iterable, Any

from entry.adapters.common import RawBatch, WorkbookSheet, RawRecord
from entry.process.cleaner import Cleaner
from entry.process.errors import InvalidSheetHeadersError, MissingRequiredValueError, DuplicateCanonicalHeaderError
from entry.process.sheet_contract import SheetIntakeContract
from entry.process.sheet_contract_config import WORKBOOK_INTAKE_CONTRACT


class ExcelValidateAndClean(Cleaner):
    def __init__(
        self,
        contracts: Mapping[
            WorkbookSheet,
            SheetIntakeContract,
        ] | None = None,
    ) -> None:
        self._contracts = dict(
            WORKBOOK_INTAKE_CONTRACT
            if contracts is None
            else contracts
        )

    def clean(
        self,
        raw: Iterable[RawBatch],
    ) -> Iterator[RawBatch]:
        for batch in raw:
            contract = self._contracts.get(batch.sheet)

            # Na obecnym etapie przetwarzamy tylko arkusze,
            # dla których zdefiniowaliśmy kontrakt wejściowy.
            if contract is None:
                continue

            cleaned_records = tuple(
                self._clean_record(
                    batch=batch,
                    record=record,
                    contract=contract,
                )
                for record in batch
            )

            if not cleaned_records:
                continue

            yield RawBatch(
                sheet=batch.sheet,
                batch_number=batch.batch_number,
                records=cleaned_records,
            )

    def _clean_record(
        self,
        *,
        batch: RawBatch,
        record: RawRecord,
        contract: SheetIntakeContract,
    ) -> RawRecord:
        cleaned_data = self._clean_row(
            sheet=batch.sheet,
            raw_data=record.data,
            contract=contract,
        )

        self._validate_required_values(
            sheet=batch.sheet,
            batch_number=batch.batch_number,
            row_number=record.row_number,
            data=cleaned_data,
            contract=contract,
        )

        return RawRecord(
            row_number=record.row_number,
            data=cleaned_data,
        )

    def _clean_row(
            self,
            *,
            sheet: WorkbookSheet,
            raw_data: Mapping[str, Any],
            contract: SheetIntakeContract,
    ) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}

        for raw_header, raw_value in raw_data.items():
            normalized_header = self._normalize_header(
                raw_header
            )

            canonical_header = (
                contract.header_aliases.get(
                    normalized_header,
                    normalized_header,
                )
            )

            if canonical_header in cleaned:
                raise DuplicateCanonicalHeaderError(
                    sheet=sheet,
                    canonical_header=canonical_header,
                )

            cleaned[canonical_header] = (
                self._clean_value(raw_value)
            )

        return cleaned

    @staticmethod
    def _validate_headers(
            *,
            sheet: WorkbookSheet,
            actual_headers: set[str],
            contract: SheetIntakeContract,
    ) -> None:
        missing_headers = set(
            contract.required_headers
            - actual_headers
        )

        unexpected_headers: set[str] = set()

        if not contract.allow_unknown_headers:
            unexpected_headers = set(
                actual_headers
                - contract.allowed_headers
            )

        if missing_headers or unexpected_headers:
            raise InvalidSheetHeadersError(
                sheet=sheet,
                missing_headers=missing_headers,
                unexpected_headers=unexpected_headers,
            )

    @staticmethod
    def _validate_required_values(
            *,
            sheet: WorkbookSheet,
            batch_number: int,
            row_number: int,
            data: Mapping[str, Any],
            contract: SheetIntakeContract,
    ) -> None:
        for field_name in contract.required_values:
            if data.get(field_name) is None:
                raise MissingRequiredValueError(
                    sheet=sheet,
                    batch_number=batch_number,
                    row_number=row_number,
                    field_name=field_name,
                )

    @staticmethod
    def _normalize_header(value: object) -> str:
        header = str(value).strip().lower()

        # Usunięcie polskich znaków z technicznej nazwy.
        header = unicodedata.normalize(
            "NFKD",
            header,
        )
        header = header.encode(
            "ascii",
            "ignore",
        ).decode("ascii")

        header = re.sub(
            r"[^a-z0-9]+",
            "_",
            header,
        )

        return header.strip("_")

    @staticmethod
    def _clean_value(value: Any) -> Any:
        if value is None:
            return None

        if (
                isinstance(value, float)
                and math.isnan(value)
        ):
            return None

        if isinstance(value, str):
            cleaned = value.replace(
                "\u00a0",
                " ",
            ).strip()

            if not cleaned:
                return None

            return cleaned

        # Daty, liczby i bool z openpyxl zachowujemy.
        return value
