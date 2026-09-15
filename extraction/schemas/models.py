from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


def id_column() -> Column:
    return Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


def reference(target: str, *, nullable: bool = False) -> Column:
    return Column(
        BigInteger,
        ForeignKey(target, ondelete="RESTRICT"),
        nullable=nullable,
    )


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
        values_callable=lambda members: [str(member.value) for member in members],
    )


class ExtractionRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionRun(SQLModel, table=True):
    """One Layer 3 extraction execution for one source-processing workflow.

    ``source_id`` and ``source_snapshot_id`` are copied from the workflow on
    creation. They intentionally remain logical cross-context references rather
    than database foreign keys, matching the Tasks/Orchestration boundary.
    """

    __tablename__ = "extraction_runs"
    __table_args__ = (
        Index("ix_extraction_runs_workflow", "workflow_id"),
        Index("ix_extraction_runs_source", "source_id"),
        Index("ix_extraction_runs_snapshot", "source_snapshot_id"),
        Index("ix_extraction_runs_status", "status"),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="extraction_runs_finished_after_started",
        ),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    workflow_id: int = Field(sa_column=reference("workflows.id"))
    source_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    source_snapshot_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    status: ExtractionRunStatus = Field(
        default=ExtractionRunStatus.RUNNING,
        sa_column=Column(
            pg_enum(ExtractionRunStatus, "extraction_run_status"),
            nullable=False,
            server_default=text("'running'"),
        ),
    )
    started_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    error_message: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=created_at_column(),
    )


class FieldObservation(SQLModel, table=True):
    """Evidence observed for one concrete business object field.

    The two tracking references are deliberately both stored:

    * ``source_field_tracking_id`` identifies the source/entity-field grouping.
    * ``source_object_field_tracking_id`` identifies the exact immutable Layer 2
      tracking version that was current while this evidence was recorded.

    This is the contract consumed by ``SourcesService._validate_observation``.
    """

    __tablename__ = "field_observations"
    __table_args__ = (
        UniqueConstraint(
            "extraction_run_id",
            "business_object_field_id",
            name="uq_field_observations_run_object_field",
        ),
        Index("ix_field_observations_run", "extraction_run_id"),
        Index("ix_field_observations_object", "business_object_id"),
        Index("ix_field_observations_object_field", "business_object_field_id"),
        Index("ix_field_observations_source_field_tracking", "source_field_tracking_id"),
        Index(
            "ix_field_observations_source_object_field_tracking",
            "source_object_field_tracking_id",
        ),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    extraction_run_id: int = Field(sa_column=reference("extraction_runs.id"))
    source_field_tracking_id: int = Field(sa_column=reference("source_field_trackings.id"))
    source_object_field_tracking_id: int = Field(
        sa_column=reference("source_object_field_trackings.id")
    )
    business_object_id: int = Field(sa_column=reference("business_objects.id"))
    business_object_field_id: int = Field(sa_column=reference("business_object_fields.id"))
    observed_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=created_at_column(),
    )


class ConcreteValue(SQLModel, table=True):
    """One raw browser/user-selected literal supporting a field observation.

    Character offsets use the half-open interval ``[char_start, char_end)``.
    ``source_snapshot_id`` is kept on each piece of evidence so provenance stays
    explicit even if the observation API later supports cross-snapshot context.
    """

    __tablename__ = "extraction_concrete_values"
    __table_args__ = (
        CheckConstraint("char_start >= 0", name="extraction_values_char_start_nonnegative"),
        CheckConstraint("char_end > char_start", name="extraction_values_char_range"),
        CheckConstraint("value_index >= 0", name="extraction_values_index_nonnegative"),
        UniqueConstraint(
            "field_observation_id",
            "value_index",
            name="uq_extraction_values_observation_index",
        ),
        Index("ix_extraction_values_observation", "field_observation_id"),
        Index("ix_extraction_values_snapshot", "source_snapshot_id"),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    field_observation_id: int = Field(sa_column=reference("field_observations.id"))
    source_snapshot_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    raw_value: str = Field(sa_column=Column(Text, nullable=False))
    char_start: int = Field(sa_column=Column(Integer, nullable=False))
    char_end: int = Field(sa_column=Column(Integer, nullable=False))
    token_class_id: str = Field(sa_column=Column(String(150), nullable=False))
    value_index: int = Field(sa_column=Column(Integer, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=created_at_column(),
    )


EXTRACTION_TABLES = (
    ExtractionRun.__table__,
    FieldObservation.__table__,
    ConcreteValue.__table__,
)
