"""Shared SCD2 writer. Caller holds the source lock and owns the transaction."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from sources.exceptions import SourceConflict
from sources.schemas.common import utc_now
from sources.schemas.models import SourceObjectFieldTracking


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def append_tracking_version(
    session: AsyncSession, row: SourceObjectFieldTracking, changes: dict, reason: str | None
) -> SourceObjectFieldTracking:
    def comparable(value):
        return as_utc(value) if isinstance(value, datetime) else value

    if all(comparable(getattr(row, key)) == comparable(value) for key, value in changes.items()):
        return row
    if row.version == 2147483647:
        raise SourceConflict("Tracking version limit reached")
    now = max(utc_now(), as_utc(row.valid_from) + timedelta(microseconds=1))
    values = row.model_dump(
        exclude={
            "id",
            "version",
            "created_at",
            "updated_at",
            "valid_from",
            "valid_to",
            "change_reason",
        }
    )
    values.update(changes)
    row.valid_to = now
    session.add(row)
    # Close first to release the partial unique indexes. Both writes remain
    # in the same transaction, so a failed insert restores the previous head.
    await session.flush()
    successor = SourceObjectFieldTracking(
        **values,
        version=row.version + 1,
        valid_from=now,
        created_at=now,
        updated_at=now,
        change_reason=reason,
    )
    session.add(successor)
    await session.flush()
    return successor
