"""Storage-agnostic asynchronous repository contracts.

These protocols define persistence capabilities only. Implementations must not
commit transactions; transaction ownership belongs to a future unit of work.
"""

from collections.abc import Sequence
from typing import Protocol


class ReadRepository[ModelT, IdentityT](Protocol):
    """Read access shared by all repository categories."""

    async def get(self, identity: IdentityT) -> ModelT | None: ...

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[ModelT]: ...


class CurrentStateRepository[ModelT, IdentityT](
    ReadRepository[ModelT, IdentityT],
    Protocol,
):
    """Repository for rows whose current state may be inserted and updated."""

    async def add(self, entity: ModelT) -> ModelT: ...

    async def save(self, entity: ModelT) -> ModelT: ...


class SoftDeleteRepository[ModelT, IdentityT](
    CurrentStateRepository[ModelT, IdentityT],
    Protocol,
):
    """Repository for recoverable master/configuration rows."""

    async def get_including_deleted(
        self,
        identity: IdentityT,
    ) -> ModelT | None: ...

    async def soft_delete(self, identity: IdentityT) -> bool: ...

    async def restore(self, identity: IdentityT) -> ModelT | None: ...


class AppendOnlyRepository[ModelT, IdentityT](
    ReadRepository[ModelT, IdentityT],
    Protocol,
):
    """Repository for immutable history, runtime and provenance rows."""

    async def append(self, entity: ModelT) -> ModelT: ...
