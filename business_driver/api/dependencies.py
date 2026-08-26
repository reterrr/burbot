from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_business_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield the application's SQLAlchemy async session.

    The host application must expose an ``async_sessionmaker`` on
    ``app.state.db_session_factory``::

        app.state.db_session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

    Keeping the session factory in the host application makes this package
    independent from the project's concrete database bootstrap code.
    """

    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        raise RuntimeError(
            "app.state.db_session_factory is not configured. "
            "Set it to sqlalchemy.ext.asyncio.async_sessionmaker."
        )
    if not isinstance(session_factory, async_sessionmaker):
        # ``async_sessionmaker`` is subscriptable/generic in typing but is also
        # a real runtime class, so this catches accidental sync session makers.
        raise TypeError("app.state.db_session_factory must be an async_sessionmaker.")

    async with session_factory() as session:
        yield session
