from typing import Annotated, AsyncIterator

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tasks.api.database import get_session
from tasks.exceptions.exceptions import WorkflowNotFound, CurrentWorkflowNotFound, TaskNotFound, TaskConflict, \
    TaskValidationError, TaskError
from tasks.services.task import TasksService

SessionDep = Annotated[
    AsyncSession,
    Depends(get_session),
]

async def get_tasks_service(
        session: SessionDep,
) -> AsyncIterator[TasksService]:
    try:
        yield TasksService(
            session
        )

    except TaskError as error:
        status_code = 500

        if isinstance(
                error,
                (
                        WorkflowNotFound,
                        CurrentWorkflowNotFound,
                        TaskNotFound,
                ),
        ):
            status_code = 404

        elif isinstance(
                error,
                TaskConflict,
        ):
            status_code = 409

        elif isinstance(
                error,
                TaskValidationError,
        ):
            status_code = 422

        raise HTTPException(
            status_code=status_code,
            detail=str(error),
        ) from error


TasksServiceDep = Annotated[
    TasksService,
    Depends(get_tasks_service),
]
