from fastapi import APIRouter

from tasks.schemas.tasks import Task

router = APIRouter(
    prefix="/sources",
    tags=["sources"],
)


@router.post("/", response_model=Task)
async def create_source():
    pass
