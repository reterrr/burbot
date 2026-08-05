"""Reusable scopes, runtime scope occurrences, selectors and observations."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field

from ..enums import (
    BusinessEntityType,
    DiscoveryMethod,
    ObservationStatus,
    SelectorType,
)
from ..mixins import CreatedAtMixin, UpdatedAtMixin, pg_enum


class SourceScope(UpdatedAtMixin, table=True):
    __tablename__ = "source_scopes"
    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "name",
            "version",
            name="uq_source_scopes_source_name_version",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "confidence_score BETWEEN 0.0 AND 1.0",
            name="confidence_score_range",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="validity_window_order",
        ),
        Index("ix_source_scopes_source_valid_to", "source_id", "valid_to"),
        Index(
            "uq_source_scopes_one_active_version",
            "source_id",
            "name",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    source_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    parent_scope_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("source_scopes.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    entity_type: BusinessEntityType = Field(
        sa_column=Column(
            pg_enum(BusinessEntityType, "business_entity_type"),
            nullable=False,
        )
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    selector_type: SelectorType = Field(
        sa_column=Column(pg_enum(SelectorType, "selector_type"), nullable=False)
    )
    selector_string: str = Field(sa_column=Column(Text, nullable=False))
    confidence_score: float
    discovered_by: DiscoveryMethod = Field(
        sa_column=Column(
            pg_enum(DiscoveryMethod, "discovery_method"),
            nullable=False,
        )
    )
    version: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False, server_default=text("1")),
    )
    valid_from: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    valid_to: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class ScopeInstance(CreatedAtMixin, table=True):
    __tablename__ = "scope_instances"
    __table_args__ = (
        UniqueConstraint(
            "extraction_run_id",
            "scope_id",
            "root_element_id",
            name="uq_scope_instances_run_scope_root",
        ),
        CheckConstraint(
            "occurrence_index IS NULL OR occurrence_index >= 0",
            name="occurrence_index_non_negative",
        ),
        CheckConstraint(
            "confidence BETWEEN 0.0 AND 1.0",
            name="confidence_range",
        ),
        Index(
            "ix_scope_instances_run_scope_occurrence",
            "extraction_run_id",
            "scope_id",
            "occurrence_index",
        ),
        Index(
            "ix_scope_instances_parent_scope_instance_id",
            "parent_scope_instance_id",
        ),
        Index("ix_scope_instances_root_element_id", "root_element_id"),
        Index("ix_scope_instances_instance_hash", "instance_hash"),
    )

    id: int | None = Field(default=None, primary_key=True)
    scope_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("source_scopes.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    extraction_run_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    parent_scope_instance_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("scope_instances.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    root_element_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("elements.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    occurrence_index: int | None = None
    instance_hash: str | None = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )
    confidence: float


class FieldSelector(UpdatedAtMixin, table=True):
    __tablename__ = "field_selectors"
    __table_args__ = (
        UniqueConstraint(
            "scope_id",
            "target_field_id",
            "version",
            name="uq_field_selectors_scope_field_version",
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "confidence_score BETWEEN 0.0 AND 1.0",
            name="confidence_score_range",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="validity_window_order",
        ),
        Index(
            "ix_field_selectors_scope_field_valid_to",
            "scope_id",
            "target_field_id",
            "valid_to",
        ),
        Index(
            "uq_field_selectors_one_active_version",
            "scope_id",
            "target_field_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    scope_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("source_scopes.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    target_field_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("target_fields.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    selector_type: SelectorType = Field(
        sa_column=Column(pg_enum(SelectorType, "selector_type"), nullable=False)
    )
    selector_string: str = Field(sa_column=Column(Text, nullable=False))
    confidence_score: float
    discovered_by: DiscoveryMethod = Field(
        sa_column=Column(
            pg_enum(DiscoveryMethod, "discovery_method"),
            nullable=False,
        )
    )
    derived_from_pattern_instance_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("pattern_instances.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    version: int = Field(
        default=1,
        sa_column=Column(Integer, nullable=False, server_default=text("1")),
    )
    valid_from: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    valid_to: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class FieldObservation(UpdatedAtMixin, table=True):
    __tablename__ = "field_observations"
    __table_args__ = (
        CheckConstraint(
            "confidence BETWEEN 0.0 AND 1.0",
            name="confidence_range",
        ),
        CheckConstraint(
            "status NOT IN ('BOUND', 'ACCEPTED') "
            "OR num_nonnulls(project_id, operator_id, recruitment_id) = 1",
            name="bound_entity_cardinality",
        ),
        CheckConstraint(
            "supersedes_observation_id IS NULL "
            "OR supersedes_observation_id <> id",
            name="does_not_supersede_itself",
        ),
        Index(
            "ix_field_observations_run_scope_field",
            "extraction_run_id",
            "scope_instance_id",
            "target_field_id",
        ),
        Index(
            "ix_field_observations_scope_field",
            "scope_instance_id",
            "target_field_id",
        ),
        Index("ix_field_observations_project_id", "project_id"),
        Index("ix_field_observations_operator_id", "operator_id"),
        Index("ix_field_observations_recruitment_id", "recruitment_id"),
        Index("ix_field_observations_status", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    extraction_run_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    scope_instance_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("scope_instances.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    target_field_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("target_fields.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    concrete_value_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("concrete_values.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    project_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    operator_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("operators.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    recruitment_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("recruitments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    confidence: float
    status: ObservationStatus = Field(
        default=ObservationStatus.DETECTED,
        sa_column=Column(
            pg_enum(ObservationStatus, "observation_status"),
            nullable=False,
            server_default=text("'DETECTED'"),
        ),
    )
    supersedes_observation_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("field_observations.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    observed_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    validated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
