"""Storage-agnostic asynchronous repository contracts.

These protocols define persistence capabilities only. Implementations must not
commit transactions; transaction ownership belongs to a future unit of work.
"""

from collections.abc import Sequence
from typing import Protocol


class ReadRepository[ModelT, IdentityT](Protocol):
    """Define read access shared by all repository categories."""

    async def get(self, identity: IdentityT) -> ModelT | None:
        """Retrieve an entity by its identifier.

        :param identity: Identifier of the entity to retrieve or modify.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ModelT]:
        """List entities using offset-based pagination.

        :param limit: Maximum number of records to return.
        :param offset: Number of matching records to skip.
        :return: Matching records in deterministic repository order.
        """
        ...


class CurrentStateRepository[ModelT, IdentityT](
    ReadRepository[ModelT, IdentityT],
    Protocol,
):
    """Define persistence operations for records with mutable current state."""

    async def add(self, entity: ModelT) -> ModelT:
        """Add a new record.

        :param entity: Entity to persist.
        :return: Persisted record reflecting the completed operation.
        """
        ...

    async def save(self, entity: ModelT) -> ModelT:
        """Persist changes to an existing record.

        :param entity: Entity to persist.
        :return: Persisted record reflecting the completed operation.
        """
        ...


class SoftDeleteRepository[ModelT, IdentityT](
    CurrentStateRepository[ModelT, IdentityT],
    Protocol,
):
    """Define persistence operations for recoverable records."""

    async def get_including_deleted(
        self,
        identity: IdentityT,
    ) -> ModelT | None:
        """Retrieve a record regardless of its deletion state.

        :param identity: Identifier of the entity to retrieve or modify.
        :return: Matching record, or ``None`` when no record exists.
        """
        ...

    async def soft_delete(self, identity: IdentityT) -> bool:
        """Soft-delete a record without removing its stored data.

        :param identity: Identifier of the entity to retrieve or modify.
        :return: ``True`` when the requested state change was applied.
        """
        ...

    async def restore(self, identity: IdentityT) -> ModelT | None:
        """Restore a soft-deleted record.

        :param identity: Identifier of the entity to retrieve or modify.
        :return: Persisted record reflecting the completed operation.
        """
        ...


class AppendOnlyRepository[ModelT, IdentityT](
    ReadRepository[ModelT, IdentityT],
    Protocol,
):
    """Define persistence operations for immutable history and provenance records."""

    async def append(self, entity: ModelT) -> ModelT:
        """Append an immutable record.

        :param entity: Entity to persist.
        :return: Persisted record reflecting the completed operation.
        """
        ...
