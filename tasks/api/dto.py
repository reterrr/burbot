from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from tasks.schemas.models import TaskType, TaskReason, TaskReferenceRole, TaskReferenceType, TaskStatus, WorkflowStatus


class Pagination(BaseModel):
    offset: int = Field(
        default=0,
        ge=0,
    )

    limit: int = Field(
        default=20,
        ge=1,
        le=100,
    )


class TaskReferenceCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    role: TaskReferenceRole

    reference_type: TaskReferenceType

    reference_id: int = Field(
        gt=0,
    )

    metadata_json: dict[str, Any] | None = None


class TaskCreateRequest(BaseModel):
    source_id: int
    source_snapshot_id: int

    type: TaskType
    reason: TaskReason | None = None

    title: str | None = None
    description: str | None = None

    metadata_json: dict[str, Any] | None = None

    references: list[TaskReferenceCreate] = Field(
        default_factory=list
    )

class TaskReferenceResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    task_id: int

    role: TaskReferenceRole
    reference_type: TaskReferenceType
    reference_id: int

    metadata_json: dict[str, Any] | None

    created_at: datetime


class TaskStatusChangeRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    status: TaskStatus


class TaskResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    workflow_id: int

    type: TaskType
    reason: TaskReason | None

    status: TaskStatus

    title: str | None
    description: str | None

    metadata_json: dict[str, Any] | None

    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class TaskDetailResponse(TaskResponse):
    references: list[TaskReferenceResponse]


class TaskListResponse(BaseModel):
    items: list[TaskResponse]

    total: int
    offset: int
    limit: int


class WorkflowStartRequest(BaseModel):
    """
    Start a new processing generation for a source.

    If another ACTIVE workflow exists for the source,
    it will automatically be superseded.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    source_snapshot_id: int = Field(
        gt=0,
    )

    key: str = Field(
        default="source_processing",
        min_length=1,
        max_length=150,
    )

    metadata_json: dict[str, Any] | None = None

    tasks: list[TaskCreateRequest] = Field(
        default_factory=list,
    )


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    key: str

    source_id: int
    source_snapshot_id: int

    previous_workflow_id: int | None

    status: WorkflowStatus

    metadata_json: dict[str, Any] | None

    created_at: datetime
    completed_at: datetime | None
    superseded_at: datetime | None


class WorkflowStartResponse(BaseModel):
    workflow: WorkflowResponse

    tasks: list[TaskResponse]

    created: bool


class WorkflowListResponse(BaseModel):
    items: list[WorkflowResponse]

    total: int
    offset: int
    limit: int


class TaskInboxItem(BaseModel):
    """
    Lightweight notification-like representation.

    Enough for frontend to render:

        "Source X has something requiring attention"
    """

    task: TaskResponse

    source_id: int
    source_snapshot_id: int

    workflow_key: str


class TaskInboxResponse(BaseModel):
    items: list[TaskInboxItem]

    total: int
    offset: int
    limit: int
