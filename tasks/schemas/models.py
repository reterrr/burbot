from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


# ============================================================
# Helpers
# ============================================================


def utc_now() -> datetime:
    return datetime.now(UTC)


def created_at_column() -> Column:
    return Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


def pg_enum(enum_class: type[StrEnum], name: str) -> SAEnum:
    return SAEnum(
        enum_class,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda members: [
            str(member.value)
            for member in members
        ],
    )


# ============================================================
# Enums
# ============================================================


class WorkflowStatus(StrEnum):
    """
    ACTIVE
        Current workflow for a source.

    COMPLETED
        All relevant work for this snapshot was completed.

    SUPERSEDED
        A newer source snapshot appeared.
        Tasks from this workflow are no longer current.

    FAILED
        Workflow could not be processed.

    CANCELLED
        Explicitly cancelled by the system/user.
    """

    ACTIVE = "active"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"

    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(StrEnum):
    """
    What should actually be done.
    """

    DISCOVER_SOURCE = "discover_source"

    REVIEW_SOURCE_CHANGE = "review_source_change"

    RESOLVE_OBSERVATION = "resolve_observation"

    REVIEW_BUSINESS_OBJECT = "review_business_object"


class TaskReason(StrEnum):
    """
    Why the task was created.
    """

    SOURCE_REGISTERED = "source_registered"
    SOURCE_CHANGED = "source_changed"

    VALUE_CHANGED = "value_changed"
    VALUE_MISSING = "value_missing"
    VALUE_CONFLICT = "value_conflict"

    POSSIBLE_NEW_OBJECT = "possible_new_object"
    OBJECT_MISSING = "object_missing"

    EXTRACTION_FAILED = "extraction_failed"

    MANUAL = "manual"


class TaskReferenceRole(StrEnum):
    """
    Meaning of a reference attached to a task.
    """

    # Main thing the task operates on.
    TARGET = "target"

    # Additional data needed to perform the task.
    CONTEXT = "context"

    # Thing/event/state that caused this task to exist.
    CAUSED_BY = "caused_by"


class TaskReferenceType(StrEnum):
    SOURCE = "source"
    SOURCE_SNAPSHOT = "source_snapshot"

    EXTRACTION_RUN = "extraction_run"
    OBSERVATION = "observation"

    BUSINESS_ENTITY = "business_entity"
    BUSINESS_OBJECT = "business_object"
    BUSINESS_FIELD = "business_field"


# ============================================================
# Workflow
# ============================================================


class Workflow(SQLModel, table=True):
    """
    A processing generation for a source.

    A Workflow represents work based on one particular state
    (snapshot) of a source.

    Example:

        Source #10
            Snapshot #100
                Workflow #1  -> SUPERSEDED

            Snapshot #150
                Workflow #2  -> ACTIVE

    Tasks belonging to Workflow #1 must no longer be treated
    as current once Workflow #2 exists.

    source_id and source_snapshot_id intentionally do not have
    database foreign keys.

    They reference the Sources bounded context, while Workflow
    belongs to the Tasks/Orchestration context. This makes the
    boundary easier to split into separate services later.
    """

    __tablename__ = "workflows"

    __table_args__ = (
        # There can be only one ACTIVE workflow for a source.
        Index(
            "uq_workflows_active_source",
            "source_id",
            unique=True,
            postgresql_where=text(
                "status = 'active'"
            ),
        ),

        Index(
            "ix_workflows_source",
            "source_id",
        ),

        Index(
            "ix_workflows_snapshot",
            "source_snapshot_id",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
    )

    # Logical workflow kind.
    #
    # For now:
    #   "source_processing"
    #
    # Later you may have:
    #   "source_reprocessing"
    #   "business_review"
    #   ...
    key: str = Field(
        default="source_processing",
        sa_column=Column(
            String(150),
            nullable=False,
        ),
    )

    # Source this whole group of tasks belongs to.
    source_id: int = Field(
        sa_column=Column(
            BigInteger,
            nullable=False,
        ),
    )

    # Snapshot this workflow is based on.
    #
    # This is crucial:
    #
    # tasks are not merely about "Source #10";
    # they are about Source #10 as seen in Snapshot #150.
    source_snapshot_id: int = Field(
        sa_column=Column(
            BigInteger,
            nullable=False,
        ),
    )

    # Allows us to keep:
    #
    # Workflow #1
    #     ↓
    # Workflow #2
    #     ↓
    # Workflow #3
    #
    # for one source.
    previous_workflow_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey(
                "workflows.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
    )

    status: WorkflowStatus = Field(
        default=WorkflowStatus.ACTIVE,
        sa_column=Column(
            pg_enum(
                WorkflowStatus,
                "workflow_status",
            ),
            nullable=False,
            server_default=WorkflowStatus.ACTIVE.value,
        ),
    )

    metadata_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            JSONB,
            nullable=True,
        ),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=created_at_column(),
    )

    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )

    superseded_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )


# ============================================================
# Task
# ============================================================


class Task(SQLModel, table=True):
    """
    Concrete unit of work inside a Workflow.

    The Workflow determines:
        which source generation this work belongs to.

    Task determines:
        what exactly should be done.

    Domain objects required by the task are attached through
    TaskReference.
    """

    __tablename__ = "tasks"

    __table_args__ = (
        Index(
            "ix_tasks_status",
            "status",
        ),
        Index(
            "ix_tasks_workflow_status",
            "workflow_id",
            "status",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
    )

    workflow_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey(
                "workflows.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
    )

    type: TaskType = Field(
        sa_column=Column(
            pg_enum(
                TaskType,
                "task_type",
            ),
            nullable=False,
        ),
    )

    reason: TaskReason | None = Field(
        default=None,
        sa_column=Column(
            pg_enum(
                TaskReason,
                "task_reason",
            ),
            nullable=True,
        ),
    )

    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        sa_column=Column(
            pg_enum(
                TaskStatus,
                "task_status",
            ),
            nullable=False,
            server_default=TaskStatus.PENDING.value,
        ),
    )

    title: str | None = Field(
        default=None,
        sa_column=Column(
            String(255),
            nullable=True,
        ),
    )

    description: str | None = Field(
        default=None,
        sa_column=Column(
            Text,
            nullable=True,
        ),
    )

    metadata_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            JSONB,
            nullable=True,
        ),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=created_at_column(),
    )

    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )

    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )


# ============================================================
# Task Reference
# ============================================================


class TaskReference(SQLModel, table=True):
    """
    Domain data used by a Task.

    Example:

        Workflow:
            Source #10
            Snapshot #150

        Task:
            REVIEW_SOURCE_CHANGE

        References:
            TARGET:
                BusinessObject #15

            CONTEXT:
                Observation #91

            CAUSED_BY:
                Observation #105

    Note that Source/Snapshot normally do not even have to be
    repeated here because they already belong to Workflow.

    They CAN still be referenced if a particular task needs them
    explicitly.
    """

    __tablename__ = "task_references"

    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "role",
            "reference_type",
            "reference_id",
            name="uq_task_reference",
        ),
        Index(
            "ix_task_references_task",
            "task_id",
        ),
        Index(
            "ix_task_references_target",
            "reference_type",
            "reference_id",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
    )

    task_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey(
                "tasks.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
    )

    role: TaskReferenceRole = Field(
        sa_column=Column(
            pg_enum(
                TaskReferenceRole,
                "task_reference_role",
            ),
            nullable=False,
        ),
    )

    reference_type: TaskReferenceType = Field(
        sa_column=Column(
            pg_enum(
                TaskReferenceType,
                "task_reference_type",
            ),
            nullable=False,
        ),
    )

    reference_id: int = Field(
        sa_column=Column(
            BigInteger,
            nullable=False,
        ),
    )

    metadata_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            JSONB,
            nullable=True,
        ),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=created_at_column(),
    )
