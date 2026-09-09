"""Source registration and lifecycle operations for the modular monolith."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from sources.exceptions import InvalidSourceFile, SourceConflict, SourceNotFound
from sources.schemas.api import (
    Pagination,
    SourceCreateRequest,
    SourceListRequest,
    SourceListResponse,
    SourceResponse,
    SourceStateChangeRequest,
    SourceStateHistoryListResponse,
    SourceStateHistoryResponse,
    SourceUpdateRequest,
)
from sources.schemas.common import utc_now
from sources.schemas.enums import SourceState, SourceStateTrigger, SourceType
from sources.schemas.models import Source, SourceStateHistory
from sources.services.lifecycle import can_transition
from sources.services.repositories import SourceRepository


def _duplicate_url(error: IntegrityError) -> bool:
    original = error.orig
    diagnostic = getattr(original, "diag", None) or getattr(original, "__cause__", None)
    constraint = getattr(diagnostic, "constraint_name", None)
    return constraint in {"uq_sources_url", "sources_url_key"} or (
        getattr(original, "sqlite_errorcode", None) == 2067 and "sources.url" in str(original)
    )


class SourcesService:
    """Each mutation commits source changes and history in one transaction.

    Use a request/activity-scoped session. This service owns its transaction;
    callers must not combine unrelated pending writes in the same session.
    Registration never fetches a URL, starts Temporal, or creates a task.
    """

    def __init__(
        self,
        session: AsyncSession,
        repository: SourceRepository | None = None,
    ) -> None:
        self._session = session
        self._repository = repository or SourceRepository(session)

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        try:
            yield
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            if _duplicate_url(error):
                raise SourceConflict("A source with this URL already exists") from error
            raise
        except BaseException:
            await self._session.rollback()
            raise

    async def _get(self, source_id: int, *, for_update: bool = False) -> Source:
        source = await self._repository.get(source_id, for_update=for_update)
        if source is None:
            raise SourceNotFound(source_id)
        return source

    async def _validate_file(self, file_id: int | None, source_type: SourceType) -> None:
        if file_id is None:
            return
        file = await self._repository.get_file(file_id)
        if file is None or file.purged_at is not None:
            raise InvalidSourceFile(f"Stored file {file_id} does not exist or has been purged")
        allowed_mime_types = {
            SourceType.HTML: {"text/html", "application/xhtml+xml"},
            SourceType.PDF: {"application/pdf"},
        }
        if file.mime_type.split(";", 1)[0].strip().lower() not in allowed_mime_types[source_type]:
            raise InvalidSourceFile(f"Stored file {file_id} does not match type {source_type}")

    async def create_source(self, request: SourceCreateRequest) -> SourceResponse:
        async with self._transaction():
            await self._validate_file(request.file_id, request.source_type)
            now = utc_now()
            source = await self._repository.add(
                Source(
                    url=str(request.url),
                    source_type=request.source_type,
                    file_id=request.file_id,
                    state=SourceState.UNDISCOVERED,
                    created_at=now,
                    updated_at=now,
                    last_state_change_at=now,
                )
            )
            self._repository.add_history(
                SourceStateHistory(
                    source_id=source.id,
                    from_state=None,
                    to_state=SourceState.UNDISCOVERED,
                    changed_at=now,
                    reason="Source registered",
                    triggered_by=SourceStateTrigger.USER,
                )
            )
            result = SourceResponse.model_validate(source)
        return result

    async def get_source(self, source_id: int) -> SourceResponse:
        return SourceResponse.model_validate(await self._get(source_id))

    async def list_sources(self, request: SourceListRequest) -> SourceListResponse:
        items, total = await self._repository.list(request)
        return SourceListResponse(
            items=[SourceResponse.model_validate(item) for item in items],
            total=total,
            offset=request.offset,
            limit=request.limit,
        )

    async def update_source(
        self,
        source_id: int,
        request: SourceUpdateRequest,
    ) -> SourceResponse:
        async with self._transaction():
            source = await self._get(source_id, for_update=True)
            if source.state != SourceState.UNDISCOVERED or await self._repository.has_state_changes(
                source_id
            ):
                raise SourceConflict(
                    "Registration details can only change before the first state change"
                )
            changes = request.model_dump(exclude_unset=True)
            if "url" in changes:
                changes["url"] = str(changes["url"])
            await self._validate_file(
                changes.get("file_id", source.file_id),
                changes.get("source_type", source.source_type),
            )
            for field, value in changes.items():
                setattr(source, field, value)
            source.updated_at = utc_now()
            await self._session.flush()
            result = SourceResponse.model_validate(source)
        return result

    def _change_state(
        self,
        source: Source,
        state: SourceState,
        reason: str | None,
        triggered_by: SourceStateTrigger,
    ) -> None:
        if not can_transition(source.state, state):
            raise SourceConflict(f"Cannot transition from {source.state} to {state}")
        if source.state == state:
            return
        now = utc_now()
        self._repository.add_history(
            SourceStateHistory(
                source_id=source.id,
                from_state=source.state,
                to_state=state,
                changed_at=now,
                reason=reason,
                triggered_by=triggered_by,
            )
        )
        source.state = state
        source.last_state_change_at = now
        source.updated_at = now

    async def change_state(
        self,
        source_id: int,
        request: SourceStateChangeRequest,
    ) -> SourceResponse:
        async with self._transaction():
            source = await self._get(source_id, for_update=True)
            if source.state != request.expected_state:
                raise SourceConflict(
                    f"Expected state {request.expected_state}, current state is {source.state}"
                )
            self._change_state(source, request.state, request.reason, request.triggered_by)
            result = SourceResponse.model_validate(source)
        return result

    async def archive_source(self, source_id: int) -> None:
        async with self._transaction():
            source = await self._get(source_id, for_update=True)
            self._change_state(
                source,
                SourceState.ARCHIVED,
                "Source archived",
                SourceStateTrigger.USER,
            )

    async def get_state_history(
        self,
        source_id: int,
        request: Pagination,
    ) -> SourceStateHistoryListResponse:
        await self._get(source_id)
        items, total = await self._repository.history(source_id, request)
        return SourceStateHistoryListResponse(
            items=[SourceStateHistoryResponse.model_validate(item) for item in items],
            total=total,
            offset=request.offset,
            limit=request.limit,
        )
