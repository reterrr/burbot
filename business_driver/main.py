from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from business_driver import business_router


load_dotenv()


DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Саме цю фабрику використовує get_business_session().
    app.state.db_session_factory = session_factory

    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(
    title="Burbot API",
    version="1.0.0",
    lifespan=lifespan,
)

# Router уже має prefix="/api/business",
# тому додатковий prefix тут не потрібен.
app.include_router(business_router)


@app.get("/health", tags=["System"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

def main() -> None:
    import uvicorn

    uvicorn.run(
        "business_driver.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()