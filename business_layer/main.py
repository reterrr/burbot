from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from business_layer.api.routes import router as business_router
from shared.database import engine
from sources.api.routes import router as sources_router


@asynccontextmanager
async def lifespan(
        app: FastAPI,
) -> AsyncIterator[None]:
    yield

    await engine.dispose()


app = FastAPI(
    title="Burbot API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(
    business_router,
    prefix="/api/v1",
)

app.include_router(sources_router, prefix="/api/v1")


@app.get(
    "/health",
    tags=["system"],
)
async def health() -> dict[str, str]:
    return {
        "status": "ok",
    }


def main():
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
    )


if __name__ == "__main__":
    main()
