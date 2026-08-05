"""Repository interfaces for sources, files, snapshots and extraction runs."""

from collections.abc import Sequence
from typing import Protocol

from ..db import (
    CheckSchedule,
    ExtractionRun,
    Source,
    SourceMetadata,
    SourceSnapshot,
    SourceStateHistory,
    SourceWarning,
    StoredFile,
)
from ..db.enums import ExtractionRunStatus, SourceState, WarningStatus
from .base import CurrentStateRepository, ReadRepository


class StoredFileRepository(ReadRepository[StoredFile, int], Protocol):
    """Define persistence operations for stored file records."""

    async def add(self, stored_file: StoredFile) -> StoredFile:
        """Add a new record.

        :param stored_file: Stored file value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def get_by_storage_key(self, storage_key: str) -> StoredFile | None:
        """Retrieve a record by storage key.

        :param storage_key: Storage key used for lookup or storage.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def find_by_sha256(self, sha256: str) -> Sequence[StoredFile]:
        """Find records by sha256.

        :param sha256: Sha256 value.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def mark_purged(self, stored_file_id: int) -> StoredFile | None:
        """Mark stored content as purged.

        :param stored_file_id: Identifier of the stored file.
        :return: Result of the operation.
        """
        ...


class SourceRepository(CurrentStateRepository[Source, int], Protocol):
    """Define persistence operations for source records."""

    async def get_by_url(self, url: str) -> Source | None:
        """Retrieve a record by url.

        :param url: Url value.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_by_state(
        self,
        state: SourceState,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Source]:
        """List records filtered by state.

        :param state: State value.
        :param limit: Maximum number of records to return.
        :param offset: Number of matching records to skip.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def append_state(
        self,
        transition: SourceStateHistory,
    ) -> SourceStateHistory:
        """Append state.

        :param transition: Transition value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def list_state_history(
        self,
        source_id: int,
    ) -> Sequence[SourceStateHistory]:
        """List state history.

        :param source_id: Identifier of the source.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def get_metadata(self, source_id: int) -> SourceMetadata | None:
        """Retrieve metadata.

        :param source_id: Identifier of the source.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def put_metadata(self, metadata: SourceMetadata) -> SourceMetadata:
        """Create or update metadata.

        :param metadata: Metadata value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def get_schedule(self, source_id: int) -> CheckSchedule | None:
        """Retrieve schedule.

        :param source_id: Identifier of the source.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def put_schedule(self, schedule: CheckSchedule) -> CheckSchedule:
        """Create or update schedule.

        :param schedule: Schedule value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def list_due(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[CheckSchedule]:
        """List sources whose scheduled check is due.

        :param limit: Maximum number of records to return.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def add_warning(self, warning: SourceWarning) -> SourceWarning:
        """Add warning.

        :param warning: Warning value.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def list_warnings(
        self,
        source_id: int,
        *,
        status: WarningStatus | None = None,
    ) -> Sequence[SourceWarning]:
        """List warnings.

        :param source_id: Identifier of the source.
        :param status: Status value.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def resolve_warning(self, warning_id: int) -> SourceWarning | None:
        """Resolve warning.

        :param warning_id: Identifier of the warning.
        :return: Result of the operation.
        """
        ...


class SourceSnapshotRepository(ReadRepository[SourceSnapshot, int], Protocol):
    """Define persistence operations for source snapshot records."""

    async def append(
        self,
        snapshot: SourceSnapshot,
        *,
        idempotency_key: str | None = None,
    ) -> SourceSnapshot:
        """Append an immutable record.

        :param snapshot: Snapshot value.
        :param idempotency_key: Idempotency key used for lookup or storage.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> SourceSnapshot | None:
        """Retrieve a record by idempotency key.

        :param idempotency_key: Idempotency key used for lookup or storage.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_for_source(
        self,
        source_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[SourceSnapshot]:
        """List records belonging to source.

        :param source_id: Identifier of the source.
        :param limit: Maximum number of records to return.
        :param offset: Number of matching records to skip.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def get_current(self, source_id: int) -> SourceSnapshot | None:
        """Retrieve current.

        :param source_id: Identifier of the source.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def set_current(
        self,
        source_id: int,
        snapshot_id: int,
    ) -> SourceSnapshot:
        """Set current.

        :param source_id: Identifier of the source.
        :param snapshot_id: Identifier of the snapshot.
        :return: Result of the operation.
        """
        ...

    async def mark_content_purged(
        self,
        snapshot_id: int,
    ) -> SourceSnapshot | None:
        """Mark snapshot content as purged.

        :param snapshot_id: Identifier of the snapshot.
        :return: Result of the operation.
        """
        ...


class ExtractionRunRepository(
    CurrentStateRepository[ExtractionRun, int],
    Protocol,
):
    """Define persistence operations for extraction run records."""

    async def add(
        self,
        run: ExtractionRun,
        *,
        idempotency_key: str | None = None,
    ) -> ExtractionRun:
        """Add a new record.

        :param run: Run value.
        :param idempotency_key: Idempotency key used for lookup or storage.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ExtractionRun | None:
        """Retrieve a record by idempotency key.

        :param idempotency_key: Idempotency key used for lookup or storage.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list_for_snapshot(
        self,
        snapshot_id: int,
        *,
        status: ExtractionRunStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtractionRun]:
        """List records belonging to snapshot.

        :param snapshot_id: Identifier of the snapshot.
        :param status: Status value.
        :param limit: Maximum number of records to return.
        :param offset: Number of matching records to skip.
        :return: Matching records in deterministic repository order.
        """
        ...

    async def list_by_status(
        self,
        status: ExtractionRunStatus,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtractionRun]:
        """List records filtered by status.

        :param status: Status value.
        :param limit: Maximum number of records to return.
        :param offset: Number of matching records to skip.
        :return: Matching records in deterministic repository order.
        """
        ...
