"""Sources, stored payloads, snapshots, health and extraction executions."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from sources.schemas.models import (
    Source as Source,
)
from sources.schemas.models import (
    SourceStateHistory as SourceStateHistory,
)
from sources.schemas.models import (
    StoredFile as StoredFile,
)

from ..enums import (
    ExtractionRunStatus,
    WarningSeverity,
    WarningStatus,
)
from ..mixins import (
    CreatedAtMixin,
    SoftDeleteMixin,
    UpdatedAtMixin,
    pg_enum,
)


class SourceMetadata(UpdatedAtMixin, table=True):
    """Store the latest hashes and robots.txt assessment for a sources.

    :ivar source_id: Identifier of the related sources.
    :ivar latest_content_hash: Latest content hash.
    :ivar latest_structure_hash: Latest structure hash.
    :ivar hashes_updated_at: Timestamp for hashes updated.
    :ivar robots_txt_checked: Robots txt checked.
    :ivar robots_txt_allows: Robots txt allows.
    :ivar robots_txt_checked_at: Timestamp for robots txt checked.
    """
    __tablename__ = "source_metadata"

    source_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sources.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        )
    )
    latest_content_hash: str | None = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )
    latest_structure_hash: str | None = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )
    hashes_updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    robots_txt_checked: bool = Field(
        default=False,
        sa_column=Column(
            Boolean,
            nullable=False,
            server_default=text("false"),
        ),
    )
    robots_txt_allows: bool | None = None
    robots_txt_checked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class CheckSchedule(UpdatedAtMixin, table=True):
    """Store adaptive polling state for a monitored sources.

    :ivar source_id: Identifier of the related sources.
    :ivar interval_seconds: Interval seconds.
    :ivar last_checked_at: Timestamp for last checked.
    :ivar next_check_at: Timestamp for next check.
    :ivar change_frequency_score: Change frequency score.
    :ivar consecutive_no_change_count: Consecutive no change count.
    :ivar enabled: Enabled.
    """
    __tablename__ = "check_schedules"
    __table_args__ = (
        CheckConstraint("interval_seconds > 0", name="interval_seconds_positive"),
        CheckConstraint(
            "change_frequency_score IS NULL "
            "OR change_frequency_score BETWEEN 0.0 AND 1.0",
            name="change_frequency_score_range",
        ),
        CheckConstraint(
            "consecutive_no_change_count >= 0",
            name="consecutive_no_change_count_non_negative",
        ),
        Index(
            "ix_check_schedules_due",
            "next_check_at",
            postgresql_where=text("enabled"),
        ),
    )

    source_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sources.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        )
    )
    interval_seconds: int
    last_checked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    next_check_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    change_frequency_score: float | None = None
    consecutive_no_change_count: int = Field(
        default=0,
        sa_column=Column(Integer, nullable=False, server_default=text("0")),
    )
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    )


class SourceWarning(UpdatedAtMixin, table=True):
    """Represent a warning raised while monitoring or processing a sources.

    :ivar id: Database primary key.
    :ivar source_id: Identifier of the related sources.
    :ivar severity: Severity.
    :ivar status: Status.
    :ivar warning_type: Warning type.
    :ivar description: Human-readable description.
    :ivar details_json: Structured details data.
    :ivar resolved_at: Timestamp for resolved.
    """
    __tablename__ = "source_warnings"
    __table_args__ = (
        Index("ix_source_warnings_source_status", "source_id", "status"),
        Index("ix_source_warnings_severity_status", "severity", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    source_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
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
    warning_type: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    description: str = Field(sa_column=Column(Text, nullable=False))
    details_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    resolved_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class OperatorSource(SoftDeleteMixin, table=True):
    """Associate an operator with one of its monitored sources.

    :ivar operator_id: Identifier of the related operator.
    :ivar source_id: Identifier of the related sources.
    :ivar is_main: Whether main.
    """
    __tablename__ = "operator_sources"
    __table_args__ = (
        Index("ix_operator_sources_source_id", "source_id"),
        Index(
            "uq_operator_sources_one_main",
            "operator_id",
            unique=True,
            postgresql_where=text("is_main AND deleted_at IS NULL"),
        ),
    )

    operator_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("operators.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    source_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sources.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    is_main: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )


class ProjectSource(SoftDeleteMixin, table=True):
    """Associate a project with one of its monitored sources.

    :ivar project_id: Identifier of the related project.
    :ivar source_id: Identifier of the related sources.
    """
    __tablename__ = "project_sources"
    __table_args__ = (Index("ix_project_sources_source_id", "source_id"),)

    project_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("projects.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    source_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sources.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )


class RecruitmentSource(SoftDeleteMixin, table=True):
    """Associate a recruitment round with one of its monitored sources.

    :ivar recruitment_id: Identifier of the related recruitment.
    :ivar source_id: Identifier of the related sources.
    """
    __tablename__ = "recruitment_sources"
    __table_args__ = (Index("ix_recruitment_sources_source_id", "source_id"),)

    recruitment_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("recruitments.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    source_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sources.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )


class SourceSnapshot(CreatedAtMixin, table=True):
    """Describe an immutable result of fetching a sources.

    :ivar id: Database primary key.
    :ivar source_id: Identifier of the related sources.
    :ivar file_id: Identifier of the related file.
    :ivar fetched_at: Timestamp for fetched.
    :ivar http_status: Http status.
    :ivar mime_type: Mime type.
    :ivar content_hash: Content hash.
    :ivar structure_hash: Structure hash.
    :ivar parser_version: Parser version.
    :ivar is_current: Whether this record is the current version.
    :ivar content_purged_at: Timestamp for content purged.
    """
    __tablename__ = "source_snapshots"
    __table_args__ = (
        Index("ix_source_snapshots_source_fetched", "source_id", "fetched_at"),
        Index("ix_source_snapshots_source_current", "source_id", "is_current"),
        Index(
            "uq_source_snapshots_one_current",
            "source_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
        Index("ix_source_snapshots_content_hash", "content_hash"),
        Index("ix_source_snapshots_structure_hash", "structure_hash"),
    )

    id: int | None = Field(default=None, primary_key=True)
    source_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    file_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("stored_files.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    fetched_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    http_status: int | None = None
    mime_type: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    content_hash: str | None = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )
    structure_hash: str | None = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )
    parser_version: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    is_current: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    content_purged_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class ExtractionRun(UpdatedAtMixin, table=True):
    """Track one domain-level extraction execution for a snapshot.

    :ivar id: Database primary key.
    :ivar snapshot_id: Identifier of the related snapshot.
    :ivar status: Status.
    :ivar extractor_version: Extractor version.
    :ivar started_at: Timestamp for started.
    :ivar finished_at: Timestamp for finished.
    :ivar error_message: Error message.
    """
    __tablename__ = "extraction_runs"
    __table_args__ = (
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="finished_not_before_started",
        ),
        Index("ix_extraction_runs_snapshot_status", "snapshot_id", "status"),
        Index("ix_extraction_runs_started_at", "started_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    snapshot_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("source_snapshots.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    status: ExtractionRunStatus = Field(
        default=ExtractionRunStatus.PENDING,
        sa_column=Column(
            pg_enum(ExtractionRunStatus, "extraction_run_status"),
            nullable=False,
            server_default=text("'PENDING'"),
        ),
    )
    extractor_version: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    error_message: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
