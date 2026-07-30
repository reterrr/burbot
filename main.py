from pathlib import Path

from entry.adapters.excel import (
    ExcelWorkbookReader
)

reader = ExcelWorkbookReader()

iterator = reader.iter_batches(Path('import.xlsx'))

for batch in iterator:
    print(batch)
