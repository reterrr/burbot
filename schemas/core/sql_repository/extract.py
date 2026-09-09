from collections.abc import Sequence

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from schemas.core.db import (
    GeneralizedPattern,
    PatternItem,
)
from schemas.core.db.enums import ItemKind

class SqlModelPatternRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_target_field(
        self,
        target_field_id: int,
        *,
        include_deleted: bool = False,
    ) -> Sequence[GeneralizedPattern]:
        statement = (
            select(GeneralizedPattern)
            .join(
                PatternItem,
                PatternItem.pattern_id == GeneralizedPattern.id,
            )
            .where(
                PatternItem.target_field_id == target_field_id,
                PatternItem.item_kind == ItemKind.TARGET_FIELD,
            )
        )

        if not include_deleted:
            statement = statement.where(
                GeneralizedPattern.deleted_at.is_(None),
                PatternItem.deleted_at.is_(None),
            )

        statement = (
            statement
            .distinct()
            .order_by(
                GeneralizedPattern.confidence.desc().nullslast(),
                GeneralizedPattern.support.desc().nullslast(),
                GeneralizedPattern.id,
            )
        )

        result = await self._session.exec(statement)
        return tuple(result.all())