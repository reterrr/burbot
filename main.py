from pathlib import Path
from pprint import pprint

from entry.adapters.excel import ExcelWorkbookReader
from entry.process.excel_clear import ExcelValidateAndClean
from entry.process.sheet_contract_config import WORKBOOK_INTAKE_CONTRACT

reader = ExcelWorkbookReader()
cleaner = ExcelValidateAndClean(
    WORKBOOK_INTAKE_CONTRACT
)

raw_batches = reader.iter_batches(
    Path("import.xlsx")
)

cleaned_batches = cleaner.clean(raw_batches)

for batch in cleaned_batches:
    print()
    print("=" * 80)
    print(f"Arkusz: {batch.sheet.value}")
    print(f"Partia: {batch.batch_number}")
    print(f"Liczba rekordów: {batch.size}")
    print(
        "Wiersze Excela: "
        f"{batch.first_row_number}–"
        f"{batch.last_row_number}"
    )
    print("=" * 80)

    for record in batch:
        print(f"\nWiersz {record.row_number}:")
        pprint(
            record.data,
            sort_dicts=False,
            width=120,
        )
