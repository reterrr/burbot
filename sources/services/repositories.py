"""Persistence for the source registry. Transaction boundaries belong to the service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from sources.schemas.api import Pagination, SourceListRequest
from sources.schemas.models import Source, SourceStateHistory, StoredFile


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, source_id: int, *, for_update: bool = False) -> Source | None:
        stmt = select(Source).where(col(Source.id) == source_id)
        if for_update:
            # Refresh a previously loaded object after acquiring its row lock.
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return await self._session.scalar(stmt)

    async def get_file(self, file_id: int) -> StoredFile | None:
        stmt = (
            select(StoredFile)
            .where(col(StoredFile.id) == file_id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )
        return await self._session.scalar(stmt)

    async def add(self, source: Source) -> Source:
        self._session.add(source)
        await self._session.flush()
        return source

    def add_history(self, entry: SourceStateHistory) -> None:
        self._session.add(entry)

    async def has_state_changes(self, source_id: int) -> bool:
        return bool(
            await self._session.scalar(
                select(
                    select(SourceStateHistory.id)
                    .where(
                        col(SourceStateHistory.source_id) == source_id,
                        col(SourceStateHistory.from_state).is_not(None),
                    )
                    .exists()
                )
            )
        )

    async def list(self, query: SourceListRequest) -> tuple[list[Source], int]:
        conditions = []
        if query.state is not None:
            conditions.append(col(Source.state) == query.state)
        if query.source_type is not None:
            conditions.append(col(Source.source_type) == query.source_type)
        if query.url is not None:
            conditions.append(col(Source.url) == str(query.url))
        total = await self._session.scalar(
            select(func.count()).select_from(Source).where(*conditions)
        )
        result = await self._session.scalars(
            select(Source)
            .where(*conditions)
            .order_by(col(Source.id))
            .offset(query.offset)
            .limit(query.limit)
        )
        return list(result), total or 0

    async def history(
        self,
        source_id: int,
        query: Pagination,
    ) -> tuple[list[SourceStateHistory], int]:
        condition = col(SourceStateHistory.source_id) == source_id
        total = await self._session.scalar(
            select(func.count()).select_from(SourceStateHistory).where(condition)
        )
        result = await self._session.scalars(
            select(SourceStateHistory)
            .where(condition)
            .order_by(col(SourceStateHistory.changed_at), col(SourceStateHistory.id))
            .offset(query.offset)
            .limit(query.limit)
        )
        return list(result), total or 0
