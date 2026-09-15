"""Layer 2 application service. All persistence uses its AsyncSession directly."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, col

from business_layer.schemas.models import (
    BusinessEntityField,
    BusinessObject,
    BusinessObjectField,
)
from sources.exceptions import (
    InvalidSourceFile,
    SourceConflict,
    SourceNotFound,
    SourceResourceNotFound,
    SourceValidationError,
)
from sources.schemas import api as dto
from sources.schemas.common import utc_now
from sources.schemas.enums import SourceState, SourceStateTrigger, SourceType, WarningStatus
from sources.schemas.internal import TrackingObservationUpdate
from sources.schemas.models import (
    Source,
    SourceBusinessObject,
    SourceCheckSchedule,
    SourceFieldTracking,
    SourceMetadata,
    SourceObjectFieldTracking,
    SourceSnapshot,
    SourceStateHistory,
    SourceWarning,
    StoredFile,
)
from sources.services.lifecycle import can_transition
from sources.services.tracking import append_tracking_version


def _unique_conflict(error: IntegrityError) -> str | None:
    original = error.orig
    diagnostic = getattr(original, "diag", None) or getattr(original, "__cause__", None)
    constraint = getattr(diagnostic, "constraint_name", None)
    messages = {
        "uq_sources_url": "A source with this URL already exists",
        "sources_url_key": "A source with this URL already exists",
        "uq_stored_files_storage_key": "This storage key is already registered",
        "uq_source_field_trackings_field": "This source already tracks that entity field",
        "uq_source_object_field_trackings_current_field": (
            "This source already tracks that object field; update the existing binding"
        ),
        "uq_source_object_field_trackings_current": "Tracking was changed concurrently",
        "uq_source_object_field_trackings_version": "Tracking was changed concurrently",
    }
    if constraint in messages:
        return messages[constraint]
    if getattr(original, "sqlite_errorcode", None) == 2067:
        for column, name in (
            ("sources.url", "uq_sources_url"),
            ("stored_files.storage_key", "uq_stored_files_storage_key"),
            ("source_field_trackings.source_id", "uq_source_field_trackings_field"),
            (
                "source_object_field_trackings.tracking_id",
                "uq_source_object_field_trackings_version",
            ),
            (
                "source_object_field_trackings.source_field_tracking_id",
                "uq_source_object_field_trackings_current_field",
            ),
        ):
            if column in str(original):
                return messages[name]
    return None


class SourcesService:
    """Use one session per request/activity; each mutation owns its transaction.

    Registration and configuration only persist Layer 2 data. They do not fetch,
    schedule execution, start Temporal, or write canonical business field values.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[None]:
        try:
            yield
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            message = _unique_conflict(error)
            if message:
                raise SourceConflict(message) from error
            raise
        except BaseException:
            await self._session.rollback()
            raise

    async def _get(self, source_id: int, *, for_update: bool = False) -> Source:
        statement = select(Source).where(col(Source.id) == source_id)
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        source = await self._session.scalar(statement)
        if source is None:
            raise SourceNotFound(source_id)
        return source

    async def _writable_source(self, source_id: int) -> Source:
        source = await self._get(source_id, for_update=True)
        if source.state == SourceState.ARCHIVED:
            raise SourceConflict("Source is archived")
        return source

    async def _page(self, statement, response_type, query: dto.Pagination) -> dto.Page:
        total = await self._session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        items = await self._session.scalars(statement.offset(query.offset).limit(query.limit))
        return dto.Page(
            items=[response_type.model_validate(item) for item in items],
            total=total or 0,
            offset=query.offset,
            limit=query.limit,
        )

    async def _save(self, row, response_type):
        self._session.add(row)
        await self._session.flush()
        return response_type.model_validate(row)

    async def _business_identity(self, model, identifier: int):
        row = await self._session.scalar(
            select(model)
            .where(col(model.id) == identifier)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        if row is None:
            raise SourceResourceNotFound(model.__name__, identifier)
        return row

    async def _file(self, file_id: int) -> StoredFile:
        file = await self._session.scalar(
            select(StoredFile)
            .where(col(StoredFile.id) == file_id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        if file is None:
            raise InvalidSourceFile(f"Stored file {file_id} does not exist")
        return file

    async def _validate_file(self, file_id: int | None, source_type: SourceType) -> None:
        if file_id is None:
            return
        file = await self._file(file_id)
        allowed = {
            SourceType.HTML: {"text/html", "application/xhtml+xml"},
            SourceType.PDF: {"application/pdf"},
            SourceType.XLSX: {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        }
        if file.mime_type.split(";", 1)[0].strip().lower() not in allowed[source_type]:
            raise InvalidSourceFile(f"Stored file {file_id} does not match type {source_type}")

    async def register_file(self, request: dto.StoredFileCreateRequest) -> dto.StoredFileResponse:
        async with self._transaction():
            result = await self._save(StoredFile(**request.model_dump()), dto.StoredFileResponse)
        return result

    async def get_file(self, file_id: int) -> dto.StoredFileResponse:
        file = await self._session.get(StoredFile, file_id)
        if file is None:
            raise SourceResourceNotFound("StoredFile", file_id)
        return dto.StoredFileResponse.model_validate(file)

    async def create_source(self, request: dto.SourceCreateRequest) -> dto.SourceResponse:
        async with self._transaction():
            await self._validate_file(request.file_id, request.type)
            now = utc_now()
            source = Source(
                type=request.type,
                url=str(request.url) if request.url else None,
                file_id=request.file_id,
                state=SourceState.UNDISCOVERED,
                created_at=now,
                updated_at=now,
                last_state_change_at=now,
            )
            self._session.add(source)
            await self._session.flush()
            self._session.add(SourceMetadata(source_id=source.id, created_at=now, updated_at=now))
            self._session.add(
                SourceStateHistory(
                    source_id=source.id,
                    from_state=None,
                    to_state=SourceState.UNDISCOVERED,
                    changed_at=now,
                    reason="Source registered",
                    triggered_by=SourceStateTrigger.USER,
                )
            )
            result = dto.SourceResponse.model_validate(source)
        return result

    async def get_source(self, source_id: int) -> dto.SourceResponse:
        return dto.SourceResponse.model_validate(await self._get(source_id))

    async def list_sources(self, request: dto.SourceListRequest) -> dto.SourceListResponse:
        statement = select(Source).order_by(col(Source.id))
        for key in ("state", "type", "url"):
            value = getattr(request, key)
            if value is not None:
                statement = statement.where(col(getattr(Source, key)) == str(value))
        return await self._page(statement, dto.SourceResponse, request)

    async def update_source(
        self, source_id: int, request: dto.SourceUpdateRequest
    ) -> dto.SourceResponse:
        async with self._transaction():
            source = await self._writable_source(source_id)
            changed_state = await self._session.scalar(
                select(
                    select(SourceStateHistory.id)
                    .where(
                        col(SourceStateHistory.source_id) == source_id,
                        col(SourceStateHistory.from_state).is_not(None),
                    )
                    .exists()
                )
            )
            if source.state != SourceState.UNDISCOVERED or changed_state:
                raise SourceConflict(
                    "Registration details can only change before the first state change"
                )
            changes = request.model_dump(exclude_unset=True)
            if changes.get("url") is not None:
                changes["url"] = str(changes["url"])
            file_id = changes.get("file_id", source.file_id)
            if changes.get("url", source.url) is None and file_id is None:
                raise SourceValidationError("A source requires url, file_id, or both")
            await self._validate_file(file_id, changes.get("type", source.type))
            for field, value in changes.items():
                setattr(source, field, value)
            source.updated_at = utc_now()
            result = await self._save(source, dto.SourceResponse)
        return result

    async def _change_state(
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
        self._session.add(
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
        source.last_state_change_at = source.updated_at = now
        if state == SourceState.ARCHIVED:
            await self._session.execute(
                update(SourceCheckSchedule)
                .where(
                    col(SourceCheckSchedule.source_id) == source.id,
                )
                .values(enabled=False, updated_at=now)
            )
            current = list(
                await self._session.scalars(
                    self._tracking_statement(source.id)
                    .where(
                        col(SourceObjectFieldTracking.valid_to).is_(None),
                        col(SourceObjectFieldTracking.tracking_enabled).is_(True),
                    )
                    .execution_options(populate_existing=True)
                )
            )
            for row in current:
                await self._append_tracking_version(
                    row, {"tracking_enabled": False}, "Source archived"
                )
            await self._session.execute(
                update(SourceFieldTracking)
                .where(col(SourceFieldTracking.source_id) == source.id)
                .values(tracking_enabled=False, desired_refresh_seconds=None, updated_at=now)
            )

    async def change_state(
        self, source_id: int, request: dto.SourceStateChangeRequest
    ) -> dto.SourceResponse:
        async with self._transaction():
            source = await self._get(source_id, for_update=True)
            if source.state != request.expected_state:
                raise SourceConflict(
                    f"Expected state {request.expected_state}, current state is {source.state}"
                )
            await self._change_state(source, request.state, request.reason, request.triggered_by)
            result = dto.SourceResponse.model_validate(source)
        return result

    async def archive_source(self, source_id: int) -> None:
        async with self._transaction():
            source = await self._get(source_id, for_update=True)
            await self._change_state(
                source, SourceState.ARCHIVED, "Source archived", SourceStateTrigger.USER
            )

    async def get_state_history(
        self, source_id: int, request: dto.Pagination
    ) -> dto.SourceStateHistoryListResponse:
        await self._get(source_id)
        return await self._page(
            select(SourceStateHistory)
            .where(
                col(SourceStateHistory.source_id) == source_id,
            )
            .order_by(col(SourceStateHistory.changed_at), col(SourceStateHistory.id)),
            dto.SourceStateHistoryResponse,
            request,
        )

    async def get_metadata(self, source_id: int) -> dto.SourceMetadataResponse:
        await self._get(source_id)
        metadata = await self._session.get(SourceMetadata, source_id)
        if metadata is None:
            raise SourceResourceNotFound("SourceMetadata", source_id)
        return dto.SourceMetadataResponse.model_validate(metadata)

    async def set_metadata(
        self, source_id: int, request: dto.SourceMetadataWrite
    ) -> dto.SourceMetadataResponse:
        async with self._transaction():
            await self._writable_source(source_id)
            row = await self._session.get(SourceMetadata, source_id, populate_existing=True)
            if row is None:
                row = SourceMetadata(source_id=source_id)
            values = request.model_dump()
            if values["hashes_updated_at"] is None:
                values["hashes_updated_at"] = utc_now()
            for key, value in values.items():
                setattr(row, key, value)
            row.updated_at = utc_now()
            result = await self._save(row, dto.SourceMetadataResponse)
        return result

    async def get_schedule(self, source_id: int) -> dto.SourceCheckScheduleResponse:
        await self._get(source_id)
        row = await self._session.get(SourceCheckSchedule, source_id)
        if row is None:
            raise SourceResourceNotFound("SourceCheckSchedule", source_id)
        return dto.SourceCheckScheduleResponse.model_validate(row)

    async def set_schedule(
        self, source_id: int, request: dto.SourceCheckScheduleWrite
    ) -> dto.SourceCheckScheduleResponse:
        async with self._transaction():
            await self._writable_source(source_id)
            row = await self._session.get(SourceCheckSchedule, source_id, populate_existing=True)
            if row is None:
                row = SourceCheckSchedule(source_id=source_id, **request.model_dump())
            else:
                for key, value in request.model_dump().items():
                    setattr(row, key, value)
                row.updated_at = utc_now()
            result = await self._save(row, dto.SourceCheckScheduleResponse)
        return result

    async def add_warning(
        self, source_id: int, request: dto.SourceWarningCreate
    ) -> dto.SourceWarningResponse:
        async with self._transaction():
            await self._writable_source(source_id)
            result = await self._save(
                SourceWarning(source_id=source_id, **request.model_dump()),
                dto.SourceWarningResponse,
            )
        return result

    async def list_warnings(
        self, source_id: int, request: dto.SourceWarningListRequest
    ) -> dto.Page[dto.SourceWarningResponse]:
        await self._get(source_id)
        statement = select(SourceWarning).where(col(SourceWarning.source_id) == source_id)
        for key in ("status", "severity"):
            value = getattr(request, key)
            if value is not None:
                statement = statement.where(col(getattr(SourceWarning, key)) == value)
        return await self._page(
            statement.order_by(col(SourceWarning.id)), dto.SourceWarningResponse, request
        )

    async def update_warning(
        self, source_id: int, warning_id: int, request: dto.SourceWarningUpdate
    ) -> dto.SourceWarningResponse:
        async with self._transaction():
            await self._get(source_id, for_update=True)
            row = await self._session.scalar(
                select(SourceWarning)
                .where(
                    col(SourceWarning.id) == warning_id,
                    col(SourceWarning.source_id) == source_id,
                )
                .execution_options(populate_existing=True)
            )
            if row is None:
                raise SourceResourceNotFound("SourceWarning", warning_id)
            if row.status != request.status:
                row.status = request.status
                row.resolved_at = utc_now() if request.status == WarningStatus.RESOLVED else None
                row.updated_at = utc_now()
            result = await self._save(row, dto.SourceWarningResponse)
        return result

    def _tracking_statement(self, source_id: int):
        return (
            select(SourceObjectFieldTracking)
            .join(
                SourceFieldTracking,
                col(SourceObjectFieldTracking.source_field_tracking_id)
                == col(SourceFieldTracking.id),
            )
            .where(col(SourceFieldTracking.source_id) == source_id)
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        # SQLite does not preserve tzinfo; PostgreSQL timestamptz does.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    def _tracking_response(
        self, source_id: int, row: SourceObjectFieldTracking
    ) -> dto.SourceObjectFieldTrackingResponse:
        values = row.model_dump(
            exclude={"id", "tracking_id", "source_field_tracking_id", "updated_at"}
        )
        for key, value in values.items():
            if isinstance(value, datetime):
                values[key] = self._utc(value)
        return dto.SourceObjectFieldTrackingResponse(
            id=row.tracking_id,
            version_id=row.id,
            source_id=source_id,
            is_current=row.valid_to is None,
            **values,
        )

    async def _tracking_page(
        self, source_id: int, statement, query: dto.Pagination
    ) -> dto.Page[dto.SourceObjectFieldTrackingResponse]:
        total = await self._session.scalar(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        rows = await self._session.scalars(statement.offset(query.offset).limit(query.limit))
        return dto.Page(
            items=[self._tracking_response(source_id, row) for row in rows],
            total=total or 0,
            offset=query.offset,
            limit=query.limit,
        )

    async def _object_tracking(
        self,
        source_id: int,
        tracking_id: UUID,
        *,
        at: datetime | None = None,
        version: int | None = None,
    ) -> SourceObjectFieldTracking:
        statement = self._tracking_statement(source_id).where(
            col(SourceObjectFieldTracking.tracking_id) == tracking_id
        )
        if version is not None:
            statement = statement.where(col(SourceObjectFieldTracking.version) == version)
        elif at is not None:
            statement = statement.where(
                col(SourceObjectFieldTracking.valid_from) <= at,
                or_(
                    col(SourceObjectFieldTracking.valid_to).is_(None),
                    col(SourceObjectFieldTracking.valid_to) > at,
                ),
            )
        else:
            statement = statement.where(col(SourceObjectFieldTracking.valid_to).is_(None))
        row = await self._session.scalar(statement.execution_options(populate_existing=True))
        if row is None:
            raise SourceResourceNotFound("SourceObjectFieldTracking", tracking_id)
        return row

    async def _ensure_tracking_context(
        self, source_id: int, object_field_id: int
    ) -> SourceFieldTracking:
        slot = await self._business_identity(BusinessObjectField, object_field_id)
        field = await self._business_identity(BusinessEntityField, slot.business_entity_field_id)
        obj = await self._business_identity(BusinessObject, slot.business_object_id)
        if obj.business_entity_id != field.business_entity_id:
            raise SourceValidationError(
                "Object does not belong to the entity that defines this field"
            )
        parent = await self._session.scalar(
            select(SourceFieldTracking).where(
                col(SourceFieldTracking.source_id) == source_id,
                col(SourceFieldTracking.business_entity_field_id) == field.id,
            )
        )
        if parent is None:
            parent = SourceFieldTracking(source_id=source_id, business_entity_field_id=field.id)
            self._session.add(parent)
        link = await self._session.get(SourceBusinessObject, (source_id, obj.id))
        if link is None:
            self._session.add(SourceBusinessObject(source_id=source_id, business_object_id=obj.id))
        await self._session.flush()
        return parent

    async def _refresh_field_demand(self, parent_id: int) -> None:
        """Maintain an internal aggregate of enabled current object field versions."""
        count, interval = (
            await self._session.execute(
                select(func.count(), func.min(SourceObjectFieldTracking.desired_refresh_seconds))
                .select_from(SourceObjectFieldTracking)
                .where(
                    col(SourceObjectFieldTracking.source_field_tracking_id) == parent_id,
                    col(SourceObjectFieldTracking.valid_to).is_(None),
                    col(SourceObjectFieldTracking.tracking_enabled).is_(True),
                )
            )
        ).one()
        await self._session.execute(
            update(SourceFieldTracking)
            .where(col(SourceFieldTracking.id) == parent_id)
            .values(
                tracking_enabled=count > 0, desired_refresh_seconds=interval, updated_at=utc_now()
            )
        )

    async def create_object_field_tracking(
        self, source_id: int, request: dto.SourceObjectFieldTrackingCreate
    ) -> dto.SourceObjectFieldTrackingResponse:
        async with self._transaction():
            # Every mutation of a source's bindings takes this same lock, including
            # archive, so duplicate creation and version rollover are serialized.
            await self._writable_source(source_id)
            parent = await self._ensure_tracking_context(
                source_id, request.business_object_field_id
            )
            now = utc_now()
            row = SourceObjectFieldTracking(
                source_field_tracking_id=parent.id,
                **request.model_dump(),
                version=1,
                created_at=now,
                updated_at=now,
                valid_from=now,
            )
            self._session.add(row)
            await self._session.flush()
            await self._refresh_field_demand(parent.id)
            result = self._tracking_response(source_id, row)
        return result

    async def list_object_field_trackings(
        self, source_id: int, query: dto.SourceObjectFieldTrackingListRequest
    ) -> dto.Page[dto.SourceObjectFieldTrackingResponse]:
        await self._get(source_id)
        statement = self._tracking_statement(source_id).where(
            col(SourceObjectFieldTracking.valid_to).is_(None)
        )
        if query.business_object_id is not None:
            statement = statement.join(
                BusinessObjectField,
                col(SourceObjectFieldTracking.business_object_field_id)
                == col(BusinessObjectField.id),
            ).where(col(BusinessObjectField.business_object_id) == query.business_object_id)
        for key in ("business_object_field_id", "tracking_enabled"):
            value = getattr(query, key)
            if value is not None:
                statement = statement.where(col(getattr(SourceObjectFieldTracking, key)) == value)
        return await self._tracking_page(
            source_id,
            statement.order_by(col(SourceObjectFieldTracking.tracking_id)),
            query,
        )

    async def get_object_field_tracking(
        self, source_id: int, tracking_id: UUID, *, at: datetime | None = None
    ) -> dto.SourceObjectFieldTrackingResponse:
        await self._get(source_id)
        row = await self._object_tracking(source_id, tracking_id, at=at)
        return self._tracking_response(source_id, row)

    async def list_object_field_tracking_versions(
        self, source_id: int, tracking_id: UUID, query: dto.Pagination
    ) -> dto.Page[dto.SourceObjectFieldTrackingResponse]:
        await self._get(source_id)
        await self._object_tracking(source_id, tracking_id)
        statement = (
            self._tracking_statement(source_id)
            .where(col(SourceObjectFieldTracking.tracking_id) == tracking_id)
            .order_by(col(SourceObjectFieldTracking.version))
        )
        return await self._tracking_page(source_id, statement, query)

    async def get_object_field_tracking_version(
        self, source_id: int, tracking_id: UUID, version: int
    ) -> dto.SourceObjectFieldTrackingResponse:
        await self._get(source_id)
        row = await self._object_tracking(source_id, tracking_id, version=version)
        return self._tracking_response(source_id, row)

    @staticmethod
    def _expect_tracking_version(row: SourceObjectFieldTracking, expected_version: int) -> None:
        if row.version != expected_version:
            raise SourceConflict(
                f"Expected tracking version {expected_version}, current version is {row.version}"
            )

    async def _append_tracking_version(
        self, row: SourceObjectFieldTracking, changes: dict, reason: str | None
    ) -> SourceObjectFieldTracking:
        return await append_tracking_version(self._session, row, changes, reason)

    async def update_object_field_tracking(
        self, source_id: int, tracking_id: UUID, request: dto.SourceObjectFieldTrackingUpdate
    ) -> dto.SourceObjectFieldTrackingResponse:
        async with self._transaction():
            await self._writable_source(source_id)
            current = await self._object_tracking(source_id, tracking_id)
            self._expect_tracking_version(current, request.expected_version)
            row = await self._append_tracking_version(
                current,
                request.model_dump(
                    exclude_unset=True, exclude={"expected_version", "change_reason"}
                ),
                request.change_reason,
            )
            await self._refresh_field_demand(row.source_field_tracking_id)
            result = self._tracking_response(source_id, row)
        return result

    async def _validate_observation(
        self, observation_id: int, tracking: SourceObjectFieldTracking
    ) -> None:
        evidence = SQLModel.metadata.tables.get("field_observations")
        required = {"id", "source_field_tracking_id", "source_object_field_tracking_id"}
        if evidence is None or not required.issubset(evidence.c.keys()):
            raise SourceConflict(
                "Layer 3 FieldObservation must be registered before setting observation references"
            )
        # Evidence refers to an exact historical version. It may be carried into
        # later versions only if that snapshot belongs to this same binding.
        observed_tracking = SourceObjectFieldTracking.__table__.alias("observed_tracking")
        valid = await self._session.scalar(
            select(evidence.c.id)
            .join(
                observed_tracking,
                evidence.c.source_object_field_tracking_id == observed_tracking.c.id,
            )
            .where(
                evidence.c.id == observation_id,
                evidence.c.source_field_tracking_id == tracking.source_field_tracking_id,
                observed_tracking.c.source_field_tracking_id == tracking.source_field_tracking_id,
                observed_tracking.c.business_object_field_id == tracking.business_object_field_id,
                observed_tracking.c.tracking_id == tracking.tracking_id,
            )
            .with_for_update(read=True)
        )
        if valid is None:
            raise SourceValidationError(
                "Observation must belong to a version of this exact source/object/field binding"
            )

    async def record_tracking_observation(
        self, source_id: int, tracking_id: UUID, request: TrackingObservationUpdate
    ) -> dto.SourceObjectFieldTrackingResponse:
        """Internal worker operation; never exposed as a public configuration route."""
        async with self._transaction():
            await self._writable_source(source_id)
            current = await self._object_tracking(source_id, tracking_id)
            self._expect_tracking_version(current, request.expected_version)
            if not current.tracking_enabled:
                raise SourceConflict("Tracking is disabled")
            changes = request.model_dump(
                exclude_unset=True, exclude={"expected_version", "change_reason"}
            )
            for key in ("last_observation_id", "baseline_observation_id"):
                if changes.get(key) is not None:
                    await self._validate_observation(changes[key], current)
            # Recording a check never infers a changed value or advances a baseline.
            row = await self._append_tracking_version(current, changes, request.change_reason)
            result = self._tracking_response(source_id, row)
        return result

    async def create_snapshot(
        self, source_id: int, request: dto.SourceSnapshotCreate
    ) -> dto.SourceSnapshotResponse:
        async with self._transaction():
            source = await self._writable_source(source_id)
            if request.file_id is not None:
                await self._validate_file(request.file_id, source.type)
            row = SourceSnapshot(source_id=source_id, **request.model_dump())
            return await self._save(row, dto.SourceSnapshotResponse)

    async def get_snapshot(self, source_id: int, snapshot_id: int) -> dto.SourceSnapshotResponse:
        row = await self._session.get(SourceSnapshot, snapshot_id)
        if row is None or row.source_id != source_id:
            raise SourceResourceNotFound(
                f"Snapshot {snapshot_id} does not exist for source {source_id}"
            )
        return dto.SourceSnapshotResponse.model_validate(row)
