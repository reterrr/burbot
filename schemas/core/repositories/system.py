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
    """Stored-file metadata; payload bytes belong to a storage adapter."""

    async def add(self, stored_file: StoredFile) -> StoredFile: ...

    async def get_by_storage_key(self, storage_key: str) -> StoredFile | None: ...

    async def find_by_sha256(self, sha256: str) -> Sequence[StoredFile]: ...

    async def mark_purged(self, stored_file_id: int) -> StoredFile | None: ...


class SourceRepository(CurrentStateRepository[Source, int], Protocol):
    """Source aggregate with metadata, schedule, state history and warnings."""

    async def get_by_url(self, url: str) -> Source | None: ...

    async def list_by_state(
        self,
        state: SourceState,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Source]: ...

    async def append_state(
        self,
        transition: SourceStateHistory,
    ) -> SourceStateHistory: ...

    async def list_state_history(
        self,
        source_id: int,
    ) -> Sequence[SourceStateHistory]: ...

    async def get_metadata(self, source_id: int) -> SourceMetadata | None: ...

    async def put_metadata(self, metadata: SourceMetadata) -> SourceMetadata: ...

    async def get_schedule(self, source_id: int) -> CheckSchedule | None: ...

    async def put_schedule(self, schedule: CheckSchedule) -> CheckSchedule: ...

    async def list_due(
        self,
        *,
        limit: int = 100,
    ) -> Sequence[CheckSchedule]: ...

    async def add_warning(self, warning: SourceWarning) -> SourceWarning: ...

    async def list_warnings(
        self,
        source_id: int,
        *,
        status: WarningStatus | None = None,
    ) -> Sequence[SourceWarning]: ...

    async def resolve_warning(self, warning_id: int) -> SourceWarning | None: ...


class SourceSnapshotRepository(ReadRepository[SourceSnapshot, int], Protocol):
    """Immutable fetch outcomes plus the mutable current/purge markers."""

    async def append(
        self,
        snapshot: SourceSnapshot,
        *,
        idempotency_key: str | None = None,
    ) -> SourceSnapshot: ...

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> SourceSnapshot | None: ...

    async def list_for_source(
        self,
        source_id: int,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[SourceSnapshot]: ...

    async def get_current(self, source_id: int) -> SourceSnapshot | None: ...

    async def set_current(
        self,
        source_id: int,
        snapshot_id: int,
    ) -> SourceSnapshot: ...

    async def mark_content_purged(
        self,
        snapshot_id: int,
    ) -> SourceSnapshot | None: ...


class ExtractionRunRepository(
    CurrentStateRepository[ExtractionRun, int],
    Protocol,
):
    """Domain extraction executions, independent from Temporal attempts."""

    async def add(
        self,
        run: ExtractionRun,
        *,
        idempotency_key: str | None = None,
    ) -> ExtractionRun: ...

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ExtractionRun | None: ...

    async def list_for_snapshot(
        self,
        snapshot_id: int,
        *,
        status: ExtractionRunStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtractionRun]: ...

    async def list_by_status(
        self,
        status: ExtractionRunStatus,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ExtractionRun]: ...
