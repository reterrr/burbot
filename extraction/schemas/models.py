from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
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

from extraction.schemas.common import created_at_column, id_column, pg_enum, reference, utc_now
from extraction.schemas.enums import ExtractionRunStatus, ObservationStatus


class ExtractionRun(SQLModel, table=True):
    """One Layer 3 extraction execution for one snapshot, optionally in a workflow.

    New runs validate the registered snapshot and optional workflow together.
    Source/snapshot IDs remain logical references so historical workflow evidence
    does not acquire fabricated snapshots when the capture schema is installed.
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
    workflow_id: int | None = Field(
        default=None, sa_column=reference("workflows.id", nullable=True)
    )
    extractor_version: str | None = Field(default=None, sa_column=Column(String(150)))
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
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
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
        Index(
            "uq_field_observations_run_object_field",
            "extraction_run_id",
            "business_object_field_id",
            unique=True,
            postgresql_where=text("scope_instance_id IS NULL"),
            sqlite_where=text("scope_instance_id IS NULL"),
        ),
        Index("ix_observations_scope_field", "scope_instance_id", "source_field_tracking_id"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="observations_confidence"),
        CheckConstraint(
            "(business_object_id IS NULL AND business_object_field_id IS NULL "
            "AND source_object_field_tracking_id IS NULL) OR "
            "(business_object_id IS NOT NULL AND business_object_field_id IS NOT NULL "
            "AND source_object_field_tracking_id IS NOT NULL)",
            name="observations_binding",
        ),
        CheckConstraint(
            "status NOT IN ('BOUND', 'ACCEPTED') OR business_object_id IS NOT NULL",
            name="observations_bound_status",
        ),
        CheckConstraint(
            "supersedes_observation_id IS NULL OR supersedes_observation_id <> id",
            name="observations_no_self_supersession",
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
    source_object_field_tracking_id: int | None = Field(
        default=None, sa_column=reference("source_object_field_trackings.id", nullable=True)
    )
    business_object_id: int | None = Field(
        default=None, sa_column=reference("business_objects.id", nullable=True)
    )
    business_object_field_id: int | None = Field(
        default=None, sa_column=reference("business_object_fields.id", nullable=True)
    )
    scope_instance_id: int | None = Field(
        default=None, sa_column=reference("scope_instances.id", nullable=True)
    )
    concrete_value_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey(
                "extraction_concrete_values.id",
                use_alter=True,
                name="fk_observation_concrete_value",
                ondelete="RESTRICT",
            ),
        ),
    )
    confidence: float = Field(default=1.0)
    status: ObservationStatus = Field(
        default=ObservationStatus.DETECTED,
        sa_column=Column(
            pg_enum(ObservationStatus, "extraction_observation_status"),
            nullable=False,
            server_default=text("'DETECTED'"),
        ),
    )
    supersedes_observation_id: int | None = Field(
        default=None, sa_column=reference("field_observations.id", nullable=True)
    )
    validated_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    notes: str | None = Field(default=None, sa_column=Column(Text))
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
        Index("ix_extraction_values_element", "element_id"),
        Index("ix_extraction_values_hash", "value_hash"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="values_confidence"),
        CheckConstraint("(char_start IS NULL) = (char_end IS NULL)", name="values_complete_range"),
        CheckConstraint(
            "NOT is_semantic_null OR normalized_value IS NULL", name="values_explicit_null"
        ),
        CheckConstraint(
            "element_id IS NOT NULL OR field_observation_id IS NOT NULL", name="values_provenance"
        ),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    field_observation_id: int | None = Field(
        default=None, sa_column=reference("field_observations.id", nullable=True)
    )
    element_id: int | None = Field(default=None, sa_column=reference("elements.id", nullable=True))
    source_snapshot_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    raw_value: str = Field(sa_column=Column(Text, nullable=False))
    char_start: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    char_end: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    token_class_id: str = Field(
        sa_column=Column(
            String(150), ForeignKey("token_classes.id", ondelete="RESTRICT"), nullable=False
        )
    )
    value_index: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    normalized_value: str | None = Field(default=None, sa_column=Column(Text))
    is_semantic_null: bool = Field(default=False)
    value_hash: str | None = Field(default=None, sa_column=Column(String(64)))
    confidence: float = Field(default=1.0)
    discovered_by: str = Field(default="MANUAL", sa_column=Column(String(30), nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=created_at_column(),
    )


from extraction.schemas.evidence import EVIDENCE_TABLES  # noqa: E402

EXTRACTION_TABLES = (
    *EVIDENCE_TABLES,
    ExtractionRun.__table__,
    FieldObservation.__table__,
    ConcreteValue.__table__,
)
