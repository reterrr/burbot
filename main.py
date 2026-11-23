import uvicorn
from fastapi import Depends, FastAPI

from business_layer.api.routes import router as business_router
from extension_sync.api import router as extension_sync_router
from extraction.api.routes import capture_router
from extraction.api.routes import router as extraction_router
from monitoring.api import operator
from monitoring.api import router as monitoring_router
from sources.api.routes import router as source_router
from tasks.api.routes import router as task_router

api = FastAPI()


api.include_router(business_router, prefix="/api/v1")
api.include_router(source_router, prefix="/api/v1")
api.include_router(task_router, dependencies=[Depends(operator)])
api.include_router(extraction_router)
api.include_router(capture_router)
api.include_router(monitoring_router)
api.include_router(extension_sync_router)


def main():
    uvicorn.run(api, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
