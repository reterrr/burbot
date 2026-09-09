from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import (
    func,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from tasks.api import dto
from tasks.exceptions.exceptions import (
    CurrentWorkflowNotFound,
    TaskConflict,
    TaskNotFound,
    TaskValidationError,
    WorkflowNotFound,
)

from tasks.schemas.models import (
    Workflow,
    WorkflowStatus,
    Task,
    TaskStatus,
    TaskReference,
    utc_now,
)

# ============================================================
# State transitions
# ============================================================


TASK_STATUS_TRANSITIONS: dict[
    TaskStatus,
    set[TaskStatus],
] = {
    TaskStatus.PENDING: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },

    TaskStatus.IN_PROGRESS: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },

    # Allows retrying failed human work.
    TaskStatus.FAILED: {
        TaskStatus.PENDING,
        TaskStatus.IN_PROGRESS,
        TaskStatus.CANCELLED,
    },

    TaskStatus.COMPLETED: set(),

    TaskStatus.CANCELLED: set(),
}


# ============================================================
# Integrity helpers
# ============================================================


def _constraint_name(
        error: IntegrityError,
) -> str | None:
    original = error.orig

    diagnostic = (
            getattr(original, "diag", None)
            or getattr(original, "__cause__", None)
    )

    return getattr(
        diagnostic,
        "constraint_name",
        None,
    )


# ============================================================
# Service
# ============================================================


class TasksService:
    """
    Application service responsible for:

        - source processing workflows,
        - superseding old source generations,
        - task lifecycle,
        - task references,
        - notification/inbox queries.

    It deliberately does not resolve Source, Snapshot,
    Observation, or BusinessObject references.

    Those IDs belong to other bounded contexts.
    """

    def __init__(
            self,
            session: AsyncSession,
    ) -> None:
        self._session = session

    # ========================================================
    # Transaction
    # ========================================================

    @asynccontextmanager
    async def _transaction(
            self,
    ) -> AsyncIterator[None]:
        try:
            yield

            await self._session.commit()

        except IntegrityError as error:
            await self._session.rollback()

            constraint = _constraint_name(
                error
            )

            if constraint == "uq_workflows_active_source":
                raise TaskConflict(
                    "Another active workflow already exists "
                    "for this source"
                ) from error

            if constraint == "uq_task_reference":
                raise TaskConflict(
                    "This reference is already attached "
                    "to the task"
                ) from error

            raise

        except BaseException:
            await self._session.rollback()
            raise

    # ========================================================
    # Internal getters
    # ========================================================

    async def _get_workflow(
            self,
            workflow_id: int,
            *,
            for_update: bool = False,
    ) -> Workflow:
        statement = (
            select(Workflow)
            .where(
                col(Workflow.id) == workflow_id
            )
        )

        if for_update:
            statement = (
                statement
                .with_for_update()
                .execution_options(
                    populate_existing=True
                )
            )

        workflow = await self._session.scalar(
            statement
        )

        if workflow is None:
            raise WorkflowNotFound(
                workflow_id
            )

        return workflow

    async def _get_task(
            self,
            task_id: int,
            *,
            for_update: bool = False,
    ) -> Task:
        statement = (
            select(Task)
            .where(
                col(Task.id) == task_id
            )
        )

        if for_update:
            statement = (
                statement
                .with_for_update()
                .execution_options(
                    populate_existing=True
                )
            )

        task = await self._session.scalar(
            statement
        )

        if task is None:
            raise TaskNotFound(
                task_id
            )

        return task

    async def _get_current_workflow(
            self,
            source_id: int,
            *,
            for_update: bool = False,
    ) -> Workflow | None:
        statement = (
            select(Workflow)
            .where(
                col(Workflow.source_id) == source_id,
                col(Workflow.status)
                == WorkflowStatus.ACTIVE,
            )
            .order_by(
                col(Workflow.id).desc()
            )
            .limit(1)
        )

        if for_update:
            statement = (
                statement
                .with_for_update()
                .execution_options(
                    populate_existing=True
                )
            )

        return await self._session.scalar(
            statement
        )

    # ========================================================
    # Guards
    # ========================================================

    @staticmethod
    def _ensure_workflow_active(
            workflow: Workflow,
    ) -> None:
        if workflow.status != WorkflowStatus.ACTIVE:
            raise TaskConflict(
                f"Workflow {workflow.id} is no longer active"
            )

    # ========================================================
    # DTO helpers
    # ========================================================

    @staticmethod
    def _workflow_response(
            workflow: Workflow,
    ) -> dto.WorkflowResponse:
        return dto.WorkflowResponse.model_validate(
            workflow
        )

    @staticmethod
    def _task_response(
            task: Task,
    ) -> dto.TaskResponse:
        return dto.TaskResponse.model_validate(
            task
        )

    async def _task_detail_response(
            self,
            task: Task,
    ) -> dto.TaskDetailResponse:
        references = await self._session.scalars(
            select(TaskReference)
            .where(
                col(TaskReference.task_id)
                == task.id
            )
            .order_by(
                col(TaskReference.id)
            )
        )

        task_response = self._task_response(
            task
        )

        return dto.TaskDetailResponse(
            **task_response.model_dump(),
            references=[
                dto.TaskReferenceResponse.model_validate(
                    reference
                )
                for reference in references
            ],
        )

    # ========================================================
    # Task creation
    # ========================================================

    async def _create_task_row(
            self,
            workflow_id: int,
            request: dto.TaskCreateRequest,
    ) -> Task:
        task = Task(
            workflow_id=workflow_id,

            type=request.type,
            reason=request.reason,

            status=TaskStatus.PENDING,

            title=request.title,
            description=request.description,

            metadata_json=request.metadata_json,
        )

        self._session.add(
            task
        )

        await self._session.flush()

        if task.id is None:
            raise RuntimeError(
                "Task has no id after flush"
            )

        for reference_request in request.references:
            self._session.add(
                TaskReference(
                    task_id=task.id,

                    role=reference_request.role,

                    reference_type=(
                        reference_request.reference_type
                    ),

                    reference_id=(
                        reference_request.reference_id
                    ),

                    metadata_json=(
                        reference_request.metadata_json
                    ),
                )
            )

        await self._session.flush()

        return task

    # ========================================================
    # Workflow lifecycle
    # ========================================================

    async def start_source_workflow(
            self,
            source_id: int,
            request: dto.WorkflowStartRequest,
    ) -> dto.WorkflowStartResponse:
        """
        Create the current workflow for a new source snapshot.

        Important behaviour:

        Source #10
            Snapshot #100
                Workflow #1 ACTIVE

        new Snapshot #150 appears

            Workflow #1 -> SUPERSEDED
            unfinished tasks -> CANCELLED

            Workflow #2 -> ACTIVE

        Calling this method again with the SAME snapshot is
        idempotent: the existing workflow is returned.
        """

        async with self._transaction():
            current = await self._get_current_workflow(
                source_id,
                for_update=True,
            )

            # ------------------------------------------------
            # Idempotency:
            #
            # acquisition/event delivery may happen twice.
            # Do not create duplicate workflow generations.
            # ------------------------------------------------

            if (
                    current is not None
                    and current.source_snapshot_id
                    == request.source_snapshot_id
            ):
                tasks = await self._session.scalars(
                    select(Task)
                    .where(
                        col(Task.workflow_id)
                        == current.id
                    )
                    .order_by(
                        col(Task.id)
                    )
                )

                return dto.WorkflowStartResponse(
                    workflow=self._workflow_response(
                        current
                    ),
                    tasks=[
                        self._task_response(task)
                        for task in tasks
                    ],
                    created=False,
                )

            now = utc_now()

            previous_workflow_id: int | None = None

            # ------------------------------------------------
            # Supersede previous generation
            # ------------------------------------------------

            if current is not None:
                if current.id is None:
                    raise RuntimeError(
                        "Current Workflow has no id"
                    )

                previous_workflow_id = current.id

                current.status = (
                    WorkflowStatus.SUPERSEDED
                )

                current.superseded_at = now

                # Any task based on the old snapshot is stale.
                await self._session.execute(
                    update(Task)
                    .where(
                        col(Task.workflow_id)
                        == current.id,

                        col(Task.status).in_(
                            [
                                TaskStatus.PENDING,
                                TaskStatus.IN_PROGRESS,
                                TaskStatus.FAILED,
                            ]
                        ),
                    )
                    .values(
                        status=TaskStatus.CANCELLED,
                        completed_at=now,
                    )
                )

            # ------------------------------------------------
            # New generation
            # ------------------------------------------------

            workflow = Workflow(
                key=request.key,

                source_id=source_id,

                source_snapshot_id=(
                    request.source_snapshot_id
                ),

                previous_workflow_id=(
                    previous_workflow_id
                ),

                status=WorkflowStatus.ACTIVE,

                metadata_json=request.metadata_json,
            )

            self._session.add(
                workflow
            )

            await self._session.flush()

            if workflow.id is None:
                raise RuntimeError(
                    "Workflow has no id after flush"
                )

            created_tasks: list[Task] = []

            for task_request in request.tasks:
                task = await self._create_task_row(
                    workflow.id,
                    task_request,
                )

                created_tasks.append(
                    task
                )

            result = dto.WorkflowStartResponse(
                workflow=self._workflow_response(
                    workflow
                ),

                tasks=[
                    self._task_response(task)
                    for task in created_tasks
                ],

                created=True,
            )

        return result

    async def get_workflow(
            self,
            workflow_id: int,
    ) -> dto.WorkflowResponse:
        workflow = await self._get_workflow(
            workflow_id
        )

        return self._workflow_response(
            workflow
        )

    async def get_current_workflow(
            self,
            source_id: int,
    ) -> dto.WorkflowResponse:
        workflow = await self._get_current_workflow(
            source_id
        )

        if workflow is None:
            raise CurrentWorkflowNotFound(
                source_id
            )

        return self._workflow_response(
            workflow
        )

    async def list_source_workflows(
            self,
            source_id: int,
            query: dto.Pagination,
    ) -> dto.WorkflowListResponse:
        condition = (
                col(Workflow.source_id)
                == source_id
        )

        total = await self._session.scalar(
            select(func.count())
            .select_from(Workflow)
            .where(condition)
        )

        workflows = await self._session.scalars(
            select(Workflow)
            .where(condition)
            .order_by(
                col(Workflow.id).desc()
            )
            .offset(query.offset)
            .limit(query.limit)
        )

        return dto.WorkflowListResponse(
            items=[
                self._workflow_response(workflow)
                for workflow in workflows
            ],

            total=total or 0,
            offset=query.offset,
            limit=query.limit,
        )

    # ========================================================
    # Tasks
    # ========================================================

    async def create_task(
            self,
            request: dto.TaskCreateRequest,
    ) -> dto.TaskDetailResponse:
        async with self._transaction():
            workflow = await self._get_current_workflow(
                request.source_id,
                for_update=True,
            )

            # ====================================================
            # Same snapshot -> reuse current workflow
            # ====================================================

            if (
                    workflow is not None
                    and workflow.source_snapshot_id
                    == request.source_snapshot_id
            ):
                pass

            # ====================================================
            # New snapshot -> supersede old generation
            # ====================================================

            else:
                now = utc_now()

                previous_workflow_id: int | None = None

                if workflow is not None:
                    if workflow.id is None:
                        raise RuntimeError(
                            "Workflow has no id"
                        )

                    previous_workflow_id = workflow.id

                    workflow.status = (
                        WorkflowStatus.SUPERSEDED
                    )
                    workflow.superseded_at = now

                    await self._session.execute(
                        update(Task)
                        .where(
                            col(Task.workflow_id)
                            == workflow.id,

                            col(Task.status).in_(
                                [
                                    TaskStatus.PENDING,
                                    TaskStatus.IN_PROGRESS,
                                    TaskStatus.FAILED,
                                ]
                            ),
                        )
                        .values(
                            status=TaskStatus.CANCELLED,
                            completed_at=now,
                        )
                    )

                workflow = Workflow(
                    key="source_processing",

                    source_id=request.source_id,
                    source_snapshot_id=(
                        request.source_snapshot_id
                    ),

                    previous_workflow_id=(
                        previous_workflow_id
                    ),

                    status=WorkflowStatus.ACTIVE,
                )

                self._session.add(workflow)

                await self._session.flush()

            # ====================================================
            # Create task in current generation
            # ====================================================

            if workflow.id is None:
                raise RuntimeError(
                    "Workflow has no id"
                )

            task = Task(
                workflow_id=workflow.id,

                type=request.type,
                reason=request.reason,

                status=TaskStatus.PENDING,

                title=request.title,
                description=request.description,

                metadata_json=request.metadata_json,
            )

            self._session.add(task)

            await self._session.flush()

            if task.id is None:
                raise RuntimeError(
                    "Task has no id"
                )

            for reference in request.references:
                self._session.add(
                    TaskReference(
                        task_id=task.id,

                        role=reference.role,

                        reference_type=(
                            reference.reference_type
                        ),

                        reference_id=(
                            reference.reference_id
                        ),

                        metadata_json=(
                            reference.metadata_json
                        ),
                    )
                )

            await self._session.flush()

            return await self._task_detail_response(
                task
            )
    async def get_task(
            self,
            task_id: int,
    ) -> dto.TaskDetailResponse:
        task = await self._get_task(
            task_id
        )

        return await self._task_detail_response(
            task
        )

    async def list_workflow_tasks(
            self,
            workflow_id: int,
            query: dto.Pagination,
    ) -> dto.TaskListResponse:
        await self._get_workflow(
            workflow_id
        )

        condition = (
                col(Task.workflow_id)
                == workflow_id
        )

        total = await self._session.scalar(
            select(func.count())
            .select_from(Task)
            .where(condition)
        )

        tasks = await self._session.scalars(
            select(Task)
            .where(condition)
            .order_by(
                col(Task.id)
            )
            .offset(query.offset)
            .limit(query.limit)
        )

        return dto.TaskListResponse(
            items=[
                self._task_response(task)
                for task in tasks
            ],

            total=total or 0,
            offset=query.offset,
            limit=query.limit,
        )

    # ========================================================
    # Task status
    # ========================================================

    async def change_task_status(
            self,
            task_id: int,
            request: dto.TaskStatusChangeRequest,
    ) -> dto.TaskDetailResponse:
        async with self._transaction():
            task = await self._get_task(
                task_id,
                for_update=True,
            )

            workflow = await self._get_workflow(
                task.workflow_id,
                for_update=True,
            )

            # ------------------------------------------------
            # This is THE important stale-task guard.
            #
            # Even if frontend somehow still has an old task,
            # it cannot mutate it after source refresh.
            # ------------------------------------------------

            self._ensure_workflow_active(
                workflow
            )

            target_status = request.status

            if target_status == task.status:
                return await self._task_detail_response(
                    task
                )

            allowed = TASK_STATUS_TRANSITIONS[
                task.status
            ]

            if target_status not in allowed:
                raise TaskValidationError(
                    f"Cannot transition task {task.id} "
                    f"from {task.status} "
                    f"to {target_status}"
                )

            now = utc_now()

            # Retry.
            if (
                    task.status == TaskStatus.FAILED
                    and target_status
                    in {
                TaskStatus.PENDING,
                TaskStatus.IN_PROGRESS,
            }
            ):
                task.completed_at = None

                if target_status == TaskStatus.PENDING:
                    task.started_at = None

            if (
                    target_status
                    == TaskStatus.IN_PROGRESS
                    and task.started_at is None
            ):
                task.started_at = now

            if target_status in {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            }:
                if task.started_at is None:
                    task.started_at = now

                task.completed_at = now

            task.status = target_status

            await self._session.flush()

            result = await self._task_detail_response(
                task
            )

        return result

    # ========================================================
    # References
    # ========================================================

    async def add_task_reference(
            self,
            task_id: int,
            request: dto.TaskReferenceCreate,
    ) -> dto.TaskReferenceResponse:
        async with self._transaction():
            task = await self._get_task(
                task_id,
                for_update=True,
            )

            workflow = await self._get_workflow(
                task.workflow_id,
                for_update=True,
            )

            self._ensure_workflow_active(
                workflow
            )

            reference = TaskReference(
                task_id=task_id,

                role=request.role,

                reference_type=(
                    request.reference_type
                ),

                reference_id=(
                    request.reference_id
                ),

                metadata_json=(
                    request.metadata_json
                ),
            )

            self._session.add(
                reference
            )

            await self._session.flush()

            result = (
                dto.TaskReferenceResponse
                .model_validate(reference)
            )

        return result

    # ========================================================
    # Inbox / notification-like tasks
    # ========================================================

    async def get_inbox_count(
            self,
    ) -> int:
        count = await self._session.scalar(
            select(func.count())
            .select_from(Task)
            .join(
                Workflow,
                col(Workflow.id)
                == col(Task.workflow_id),
            )
            .where(
                col(Workflow.status)
                == WorkflowStatus.ACTIVE,

                col(Task.status).in_(
                    [
                        TaskStatus.PENDING,
                        TaskStatus.IN_PROGRESS,
                    ]
                ),
            )
        )

        return count or 0

    async def get_inbox(
            self,
            query: dto.Pagination,
    ) -> dto.TaskInboxResponse:
        condition = (
                col(Workflow.status)
                == WorkflowStatus.ACTIVE
        )

        task_condition = (
            col(Task.status).in_(
                [
                    TaskStatus.PENDING,
                    TaskStatus.IN_PROGRESS,
                ]
            )
        )

        total = await self._session.scalar(
            select(func.count())
            .select_from(Task)
            .join(
                Workflow,
                col(Workflow.id)
                == col(Task.workflow_id),
            )
            .where(
                condition,
                task_condition,
            )
        )

        rows = await self._session.execute(
            select(
                Task,
                Workflow,
            )
            .join(
                Workflow,
                col(Workflow.id)
                == col(Task.workflow_id),
            )
            .where(
                condition,
                task_condition,
            )
            .order_by(
                col(Task.created_at).desc()
            )
            .offset(query.offset)
            .limit(query.limit)
        )

        items: list[dto.TaskInboxItem] = []

        for task, workflow in rows:
            items.append(
                dto.TaskInboxItem(
                    task=self._task_response(
                        task
                    ),

                    source_id=(
                        workflow.source_id
                    ),

                    source_snapshot_id=(
                        workflow.source_snapshot_id
                    ),

                    workflow_key=(
                        workflow.key
                    ),
                )
            )

        return dto.TaskInboxResponse(
            items=items,

            total=total or 0,
            offset=query.offset,
            limit=query.limit,
        )
