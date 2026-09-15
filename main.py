import uvicorn
from fastapi import FastAPI

from business_layer.api.routes import router as business_router
from extraction.api.routes import router as extraction_router, capture_router
from sources.api.routes import router as source_router
from tasks.api.routes import router as task_router

api = FastAPI(prefix="/api/v1")

api.include_router(business_router)
api.include_router(source_router)
api.include_router(task_router)
api.include_router(extraction_router)
api.include_router(capture_router)


async def main():
    uvicorn.run(api, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
