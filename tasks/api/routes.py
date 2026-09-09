from fastapi import APIRouter

router = APIRouter(
    prefix="/tasks",
)

"GET /"
"GET /{task_id}"


@router.get("/{task_id}")
async def get_task(task_id: str):



    "POST /"
