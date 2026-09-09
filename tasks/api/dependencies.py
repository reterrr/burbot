from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tasks.services.task import TaskService


session = Annotated[
    AsyncSession,
    Depends()
]


def get_task_service_dep(session: AsyncSession) -> TaskService:
    return TaskService(
        session=session
    )


task_service = Annotated[
    TaskService,
    Depends(get_task_service_dep),
]
