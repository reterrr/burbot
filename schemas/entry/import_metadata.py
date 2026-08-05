"""Metadata schema describing a BUR import operation."""

# schemas/entry/import_metadata.py

from datetime import datetime

from common import BurInputModel, ExternalRef


class BurImportMetadataIn(BurInputModel):
    """Validate metadata supplied with a BUR import bundle.

    :ivar batch_ref: Stable external reference to the batch.
    :ivar schema_version: Schema version.
    :ivar source_file_name: Source file name.
    :ivar generated_at: Timestamp for generated.
    :ivar prepared_by: Prepared by.
    :ivar notes: Optional notes supplied by an operator or importer.
    """
    batch_ref: ExternalRef
    schema_version: str

    source_file_name: str
    generated_at: datetime

    prepared_by: str | None = None
    notes: str | None = None
