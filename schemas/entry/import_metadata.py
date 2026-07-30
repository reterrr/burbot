# schemas/entry/import_metadata.py

from datetime import datetime

from common import BurInputModel, ExternalRef


class BurImportMetadataIn(BurInputModel):
    batch_ref: ExternalRef
    schema_version: str

    source_file_name: str
    generated_at: datetime

    prepared_by: str | None = None
    notes: str | None = None
