"""Atomic service writes, composable inside a caller-owned transaction."""

from contextlib import asynccontextmanager


@asynccontextmanager
async def transaction(session):
    if session.in_transaction():
        async with session.begin_nested():
            yield
    else:
        async with session.begin():
            yield
