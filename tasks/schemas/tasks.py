from datetime import datetime, UTC
from enum import StrEnum, Enum, auto
from typing import Any

from anyio._backends._asyncio import TaskState
from sqlalchemy import BigInteger, Column, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Enum as SAEnum, SQLModel


class Reason(StrEnum):
    VALUE_CHANGED = "value_changed"


class TaskState(Enum):
    OPEN = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    CANCELLED = auto()


def pg_enum(enum: type[StrEnum], name: str) -> SAEnum:
    return SAEnum(

    )


def utc_now() -> datetime:
    return datetime.now(UTC)


def created_at_column() -> Column:
    return Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SubjectType(StrEnum):
    FIELD_OBSERVATION = "FIELD_OBSERVATION"


class Taskable(SQLModel, table=True):
    __tablename__ = "taskables"

    id: int = Field(Column(BigInteger, primary_key=True, autoincrement=True))
    subject_type: SubjectType = Field(default=SubjectType.FIELD_OBSERVATION,
                                      sa_column=Column(pg_enum(SubjectType, "subject_type"),
                                                       server_default=SubjectType.FIELD_OBSERVATION.value))
    subject_id: int = Field(Column(BigInteger, nullable=False, default=None))

    metadata_json: Any = Field(Column(JSONB, nullable=True, default=None))

    created_at: datetime = Field(default=utc_now, sa_column=created_at_column())


# v0.0.1 HUMAN only centered task
class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: int = Field(Column(BigInteger, primary_key=True, autoincrement=True))
    taskable_id: int = Field(sa_column=Column(BigInteger, nullable=False, default=None, foreign_key="taskables.id"))

    reason: Reason = Field(
        default=Reason.VALUE_CHANGED,
        sa_column=Column(pg_enum(Reason, "reason"), nullable=False, server_default=Reason.VALUE_CHANGED.value)
    )

    state: TaskState = Field(
        sa_column=Column()
    )

    workflow_task_key: str = Field(default=None, nullable=False)

    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())
