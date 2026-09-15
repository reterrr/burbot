"""Sources / Acquisition identities and versioned object field tracking."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from sources.schemas.common import CreatedAtMixin, UpdatedAtMixin, pg_enum, utc_now
from sources.schemas.enums import (
    SourceState,
    SourceStateTrigger,
    SourceType,
    WarningSeverity,
    WarningStatus,
)


def id_column() -> Column:
    return Column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )


def reference(target: str, *, nullable: bool = False, primary_key: bool = False) -> Column:
    return Column(
        BigInteger,
        ForeignKey(target, ondelete="RESTRICT"),
        nullable=nullable,
        primary_key=primary_key,
    )


def timestamp() -> Column:
    return Column(DateTime(timezone=True), nullable=True)


def enabled_column() -> Column:
    return Column(Boolean, nullable=False, server_default=text("true"))


class StoredFile(CreatedAtMixin, table=True):
    __tablename__ = "stored_files"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_stored_files_storage_key"),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0", name="stored_files_size_nonnegative"
        ),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    storage_key: str = Field(sa_column=Column(String, nullable=False))
    original_name: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    mime_type: str = Field(sa_column=Column(String, nullable=False))
    size_bytes: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    sha256: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))


class Source(UpdatedAtMixin, table=True):
    """An acquisition identity located by URL, stored file, or both."""

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("url", name="uq_sources_url"),
        CheckConstraint("url IS NOT NULL OR file_id IS NOT NULL", name="sources_locator_required"),
        Index("ix_sources_state", "state"),
        Index("ix_sources_type", "type"),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    type: SourceType = Field(sa_column=Column(pg_enum(SourceType, "source_type"), nullable=False))
    url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    file_id: int | None = Field(default=None, sa_column=reference("stored_files.id", nullable=True))
    state: SourceState = Field(
        default=SourceState.UNDISCOVERED,
        sa_column=Column(
            pg_enum(SourceState, "source_state"),
            nullable=False,
            server_default=text("'UNDISCOVERED'"),
        ),
    )
    last_state_change_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class SourceMetadata(UpdatedAtMixin, table=True):
    __tablename__ = "source_metadata"

    source_id: int = Field(sa_column=reference("sources.id", primary_key=True))
    latest_content_hash: str | None = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )
    latest_structure_hash: str | None = Field(
        default=None, sa_column=Column(String(64), nullable=True)
    )
    hashes_updated_at: datetime | None = Field(default=None, sa_column=timestamp())


class SourceCheckSchedule(UpdatedAtMixin, table=True):
    """One fetch cadence per source, shared by all of its tracked fields."""

    __tablename__ = "source_check_schedules"
    __table_args__ = (
        CheckConstraint("interval_seconds > 0", name="source_check_schedules_interval_positive"),
    )

    source_id: int = Field(sa_column=reference("sources.id", primary_key=True))
    interval_seconds: int = Field(sa_column=Column(Integer, nullable=False))
    last_checked_at: datetime | None = Field(default=None, sa_column=timestamp())
    next_check_at: datetime | None = Field(default=None, sa_column=timestamp())
    enabled: bool = Field(default=True, sa_column=enabled_column())


class SourceStateHistory(SQLModel, table=True):
    __tablename__ = "source_state_history"
    __table_args__ = (Index("ix_source_state_history_source_changed", "source_id", "changed_at"),)

    id: int | None = Field(default=None, sa_column=id_column())
    source_id: int = Field(sa_column=reference("sources.id"))
    from_state: SourceState | None = Field(
        default=None,
        sa_column=Column(
            pg_enum(SourceState, "source_state"),
            nullable=True,
        ),
    )
    to_state: SourceState = Field(
        sa_column=Column(pg_enum(SourceState, "source_state"), nullable=False)
    )
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    triggered_by: SourceStateTrigger = Field(
        default=SourceStateTrigger.SYSTEM,
        sa_column=Column(
            pg_enum(SourceStateTrigger, "source_state_trigger"),
            nullable=False,
            server_default=text("'SYSTEM'"),
        ),
    )
    changed_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class SourceWarning(UpdatedAtMixin, table=True):
    __tablename__ = "source_warnings"
    __table_args__ = (
        Index("ix_source_warnings_source_status", "source_id", "status"),
        Index("ix_source_warnings_severity_status", "severity", "status"),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    source_id: int = Field(sa_column=reference("sources.id"))
    severity: WarningSeverity = Field(
        default=WarningSeverity.WARNING,
        sa_column=Column(
            pg_enum(WarningSeverity, "warning_severity"),
            nullable=False,
            server_default=text("'WARNING'"),
        ),
    )
    status: WarningStatus = Field(
        default=WarningStatus.OPEN,
        sa_column=Column(
            pg_enum(WarningStatus, "warning_status"),
            nullable=False,
            server_default=text("'OPEN'"),
        ),
    )
    warning_type: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    description: str = Field(sa_column=Column(Text, nullable=False))
    details_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(
            JSONB().with_variant(JSON(), "sqlite"),
            nullable=True,
        ),
    )
    resolved_at: datetime | None = Field(default=None, sa_column=timestamp())


class SourceBusinessObject(CreatedAtMixin, table=True):
    """Internal provenance link, created when a concrete object field is tracked."""

    __tablename__ = "source_business_objects"
    __table_args__ = (Index("ix_source_business_objects_object", "business_object_id"),)

    source_id: int = Field(sa_column=reference("sources.id", primary_key=True))
    business_object_id: int = Field(sa_column=reference("business_objects.id", primary_key=True))


class SourceFieldTracking(UpdatedAtMixin, table=True):
    """Internal source + entity field grouping with aggregated current demand."""

    __tablename__ = "source_field_trackings"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "business_entity_field_id", name="uq_source_field_trackings_field"
        ),
        Index("ix_source_field_trackings_field", "business_entity_field_id"),
        CheckConstraint(
            "desired_refresh_seconds IS NULL OR desired_refresh_seconds > 0",
            name="source_field_trackings_refresh_positive",
        ),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    source_id: int = Field(sa_column=reference("sources.id"))
    business_entity_field_id: int = Field(sa_column=reference("business_entity_fields.id"))
    tracking_enabled: bool = Field(default=True, sa_column=enabled_column())
    desired_refresh_seconds: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )


class SourceObjectFieldTracking(CreatedAtMixin, table=True):
    """One SCD Type 2 snapshot of a source + object field binding.

    ``tracking_id`` identifies the binding across versions; ``id`` identifies
    this exact snapshot and remains the target of Layer 3 evidence references.
    After insertion, the service only updates ``valid_to`` to close a version.
    """

    __tablename__ = "source_object_field_trackings"
    __table_args__ = (
        Index(
            "uq_source_object_field_trackings_current_field",
            "source_field_tracking_id",
            "business_object_field_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
            sqlite_where=text("valid_to IS NULL"),
        ),
        UniqueConstraint("tracking_id", "version", name="uq_source_object_field_trackings_version"),
        Index(
            "uq_source_object_field_trackings_current",
            "tracking_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
            sqlite_where=text("valid_to IS NULL"),
        ),
        CheckConstraint("version > 0", name="source_object_field_trackings_version_positive"),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="source_object_field_trackings_valid_period",
        ),
        CheckConstraint(
            "desired_refresh_seconds IS NULL OR desired_refresh_seconds > 0",
            name="source_object_field_trackings_refresh_positive",
        ),
        Index("ix_source_object_field_trackings_object_field", "business_object_field_id"),
        Index("ix_source_object_field_trackings_enabled", "tracking_enabled"),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    tracking_id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(Uuid, nullable=False, server_default=func.gen_random_uuid()),
    )
    version: int = Field(
        default=1, sa_column=Column(Integer, nullable=False, server_default=text("1"))
    )
    valid_from: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    valid_to: datetime | None = Field(default=None, sa_column=timestamp())
    change_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    # Retain the existing column/data, but no onupdate: closing a version must
    # not alter the timestamp or payload of that snapshot.
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    source_field_tracking_id: int = Field(sa_column=reference("source_field_trackings.id"))
    business_object_field_id: int = Field(sa_column=reference("business_object_fields.id"))
    tracking_enabled: bool = Field(default=True, sa_column=enabled_column())
    desired_refresh_seconds: int | None = Field(
        default=None, sa_column=Column(Integer, nullable=True)
    )
    # Layer 3 owns the target table. register_evidence_references attaches the
    # two physical FKs when that model is present in the application's metadata.
    last_observation_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            nullable=True,
            info={"references": "field_observations.id"},
        ),
    )
    baseline_observation_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            nullable=True,
            info={"references": "field_observations.id"},
        ),
    )
    last_checked_at: datetime | None = Field(default=None, sa_column=timestamp())
    last_changed_at: datetime | None = Field(default=None, sa_column=timestamp())


SOURCE_TABLES = (
    StoredFile.__table__,
    Source.__table__,
    SourceMetadata.__table__,
    SourceCheckSchedule.__table__,
    SourceStateHistory.__table__,
    SourceWarning.__table__,
    SourceBusinessObject.__table__,
    SourceFieldTracking.__table__,
    SourceObjectFieldTracking.__table__,
)


def register_evidence_references(metadata: MetaData = SQLModel.metadata) -> bool:
    """Complete the Layer 2/3 cycle after Layer 3's real model has been imported.

    No placeholder evidence table is registered and no DDL is executed here.
    Call after loading all model modules, before Alembic autogeneration.
    """
    evidence = metadata.tables.get("field_observations")
    if evidence is None or not {
        "id",
        "source_field_tracking_id",
        "source_object_field_tracking_id",
    }.issubset(evidence.c.keys()):
        return False
    tracking = metadata.tables["source_object_field_trackings"]
    for column_name in ("last_observation_id", "baseline_observation_id"):
        if not tracking.c[column_name].foreign_keys:
            tracking.append_constraint(
                ForeignKeyConstraint(
                    [column_name],
                    ["field_observations.id"],
                    ondelete="RESTRICT",
                    use_alter=True,
                    name=f"fk_source_object_field_trackings_{column_name}",
                )
            )
    return True


class SourceSnapshot(CreatedAtMixin, table=True):
    """Immutable acquisition metadata; file_id points to the stored snapshot bytes.

    Kept separate from legacy workflow snapshot integers so old evidence is not
    retroactively assigned a fabricated snapshot.
    """

    __tablename__ = "source_snapshots"
    __table_args__ = (Index("ix_source_snapshots_source_fetched", "source_id", "fetched_at"),)
    id: int | None = Field(default=None, sa_column=id_column())
    source_id: int = Field(sa_column=reference("sources.id"))
    file_id: int | None = Field(default=None, sa_column=reference("stored_files.id", nullable=True))
    page_url: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    fetched_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    mime_type: str | None = None
    content_hash: str | None = Field(default=None, sa_column=Column(String(64)))
    structure_hash: str | None = Field(default=None, sa_column=Column(String(64)))
    parser_version: str | None = None


SOURCE_TABLES = (*SOURCE_TABLES, SourceSnapshot.__table__)
