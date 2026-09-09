from typing import Annotated

from fastapi import (
    APIRouter,
    Path,
    Query,
    status,
)

from tasks.api import dto
from tasks.api.dependencies import (
    TasksServiceDep,
)

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    responses={
        404: {
            "description": (
                "Task or workflow not found"
            )
        },
        409: {
            "description": (
                "Task/workflow is stale or "
                "conflicts with current state"
            )
        },
        422: {
            "description": (
                "Invalid task state transition"
            )
        },
    },
)

PositiveId = Annotated[
    int,
    Path(
        gt=0,
        le=9223372036854775807,
    ),
]

Pagination = Annotated[
    dto.Pagination,
    Query(),
]


# ============================================================
# Source workflows
# ============================================================


@router.post(
    "/sources/{source_id}/workflows",
    response_model=dto.WorkflowStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_source_workflow(
        source_id: PositiveId,
        request: dto.WorkflowStartRequest,
        service: TasksServiceDep,
) -> dto.WorkflowStartResponse:
    """
    Start processing a source snapshot.

    If an older ACTIVE workflow exists:

        - old workflow becomes SUPERSEDED
        - unfinished old tasks become CANCELLED
        - a new ACTIVE workflow is created

    Repeating the call for the same snapshot is idempotent.
    """

    return await service.start_source_workflow(
        source_id,
        request,
    )


@router.get(
    "/sources/{source_id}/workflows/current",
    response_model=dto.WorkflowResponse,
)
async def get_current_source_workflow(
        source_id: PositiveId,
        service: TasksServiceDep,
) -> dto.WorkflowResponse:
    return await service.get_current_workflow(
        source_id
    )


@router.get(
    "/sources/{source_id}/workflows",
    response_model=dto.WorkflowListResponse,
)
async def list_source_workflows(
        source_id: PositiveId,
        service: TasksServiceDep,
        query: Pagination,
) -> dto.WorkflowListResponse:
    return await service.list_source_workflows(
        source_id,
        query,
    )


# ============================================================
# Workflows
# ============================================================


@router.get(
    "/workflows/{workflow_id}",
    response_model=dto.WorkflowResponse,
)
async def get_workflow(
        workflow_id: PositiveId,
        service: TasksServiceDep,
) -> dto.WorkflowResponse:
    return await service.get_workflow(
        workflow_id
    )


@router.get(
    "/workflows/{workflow_id}/tasks",
    response_model=dto.TaskListResponse,
)
async def list_workflow_tasks(
        workflow_id: PositiveId,
        service: TasksServiceDep,
        query: Pagination,
) -> dto.TaskListResponse:
    return await service.list_workflow_tasks(
        workflow_id,
        query,
    )


@router.post(
    "/workflows/{workflow_id}/tasks",
    response_model=dto.TaskDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
        workflow_id: PositiveId,
        request: dto.TaskCreateRequest,
        service: TasksServiceDep,
) -> dto.TaskDetailResponse:
    return await service.create_task(
        workflow_id,
        request,
    )


# ============================================================
# Inbox
# ============================================================


@router.get(
    "/inbox/count",
    response_model=int,
)
async def get_inbox_count(
        service: TasksServiceDep,
) -> int:
    """
    Useful for frontend notification badge.
    """

    return await service.get_inbox_count()


@router.get(
    "/inbox",
    response_model=dto.TaskInboxResponse,
)
async def get_inbox(
        service: TasksServiceDep,
        query: Pagination,
) -> dto.TaskInboxResponse:
    """
    Only actionable tasks belonging to ACTIVE workflows.

    Tasks from superseded source snapshots never appear here.
    """

    return await service.get_inbox(
        query
    )


# ============================================================
# Individual tasks
# ============================================================


@router.get(
    "/{task_id}",
    response_model=dto.TaskDetailResponse,
)
async def get_task(
        task_id: PositiveId,
        service: TasksServiceDep,
) -> dto.TaskDetailResponse:
    return await service.get_task(
        task_id
    )


@router.patch(
    "/{task_id}/status",
    response_model=dto.TaskDetailResponse,
)
async def change_task_status(
        task_id: PositiveId,
        request: dto.TaskStatusChangeRequest,
        service: TasksServiceDep,
) -> dto.TaskDetailResponse:
    return await service.change_task_status(
        task_id,
        request,
    )


@router.post(
    "/{task_id}/references",
    response_model=dto.TaskReferenceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_task_reference(
        task_id: PositiveId,
        request: dto.TaskReferenceCreate,
        service: TasksServiceDep,
) -> dto.TaskReferenceResponse:
    return await service.add_task_reference(
        task_id,
        request,
    )
