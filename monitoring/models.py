"""Durable monitoring jobs and references into the existing source/evidence layers."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from extraction.schemas.common import reference, utc_now

TERMINAL = ("completed", "failed", "cancelled")
LEASED = ("claimed", "capturing", "uploading")
READY = ("pending", "retry_pending")
PROCESSABLE = ("uploaded", "processing")
ACTIVE = (*READY, *LEASED, *PROCESSABLE)
STRICT_NAVIGATION = "strict"
TRUSTED_HTTPS = "public_https"
TRUSTED_HTTP = "public_http_https"
NAVIGATION_POLICIES = (STRICT_NAVIGATION, TRUSTED_HTTPS, TRUSTED_HTTP)


def timestamp(nullable=False):
    return Column(DateTime(timezone=True), nullable=nullable)


class MonitoringSource(SQLModel, table=True):
    __tablename__ = "monitoring_sources"
    source_id: int = Field(sa_column=reference("sources.id", primary_key=True))
    url: str = Field(sa_column=Column(Text, nullable=False))
    origins: list[str] = Field(sa_column=Column(JSONB, nullable=False))
    enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))
    approved_at: datetime = Field(default_factory=utc_now, sa_column=timestamp())
    trusted_url: str | None = Field(default=None, sa_column=Column(Text))
    trusted_origin: str | None = Field(default=None, sa_column=Column(Text))


class MonitoringAgent(SQLModel, table=True):
    __tablename__ = "monitoring_agents"
    id: UUID = Field(default_factory=uuid4, sa_column=Column(Uuid, primary_key=True))
    name: str = Field(sa_column=Column(String(150), nullable=False))
    token_digest: str = Field(sa_column=Column(String(64), nullable=False, unique=True))
    enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))
    trusted: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default=text("false"))
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp())
    last_seen_at: datetime | None = Field(default=None, sa_column=timestamp(nullable=True))


class MonitoringAgentSource(SQLModel, table=True):
    __tablename__ = "monitoring_agent_sources"
    __table_args__ = (
        Index(
            "ix_monitoring_agent_sources_coverage",
            "source_id",
            "agent_id",
            postgresql_where=text("enabled"),
        ),
    )
    agent_id: UUID = Field(
        sa_column=Column(Uuid, ForeignKey("monitoring_agents.id"), primary_key=True)
    )
    source_id: int = Field(sa_column=reference("monitoring_sources.source_id", primary_key=True))
    enabled: bool = Field(
        default=True, sa_column=Column(Boolean, nullable=False, server_default=text("true"))
    )


class MonitoringJob(SQLModel, table=True):
    __tablename__ = "monitoring_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN (" + ",".join(f"'{state}'" for state in (*ACTIVE, *TERMINAL)) + ")",
            name="monitoring_job_status",
        ),
        CheckConstraint(
            "attempt_count >= 0 AND processing_attempts >= 0", name="monitoring_job_attempts"
        ),
        CheckConstraint(
            "navigation_policy IN ("
            + ",".join(f"'{value}'" for value in NAVIGATION_POLICIES)
            + ")",
            name="monitoring_job_navigation",
        ),
        Index(
            "uq_monitoring_jobs_active_source",
            "source_id",
            unique=True,
            postgresql_where=text("status NOT IN ('completed','failed','cancelled')"),
        ),
        Index("ix_monitoring_jobs_queue", "status", "available_at"),
        Index("ix_monitoring_jobs_source_created", "source_id", "created_at", "id"),
    )
    id: UUID = Field(default_factory=uuid4, sa_column=Column(Uuid, primary_key=True))
    source_id: int = Field(sa_column=reference("monitoring_sources.source_id"))
    url: str = Field(sa_column=Column(Text, nullable=False))
    origins: list[str] = Field(sa_column=Column(JSONB, nullable=False))
    navigation_policy: str = Field(
        default=STRICT_NAVIGATION,
        sa_column=Column(String(24), nullable=False, server_default=text("'strict'")),
    )
    reason: str = Field(sa_column=Column(String(32), nullable=False))
    status: str = Field(default="pending", sa_column=Column(String(32), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp())
    available_at: datetime = Field(default_factory=utc_now, sa_column=timestamp())
    agent_id: UUID | None = Field(
        default=None, sa_column=Column(Uuid, ForeignKey("monitoring_agents.id"))
    )
    lease_id: UUID | None = Field(default=None, sa_column=Column(Uuid))
    claimed_at: datetime | None = Field(default=None, sa_column=timestamp(nullable=True))
    lease_expires_at: datetime | None = Field(default=None, sa_column=timestamp(nullable=True))
    completed_at: datetime | None = Field(default=None, sa_column=timestamp(nullable=True))
    attempt_count: int = 0
    processing_attempts: int = 0
    source_snapshot_id: int | None = Field(
        default=None, sa_column=reference("source_snapshots.id", nullable=True)
    )
    extraction_run_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("extraction_runs.id"), nullable=True, unique=True),
    )
    completion_key: UUID | None = Field(default=None, sa_column=Column(Uuid))
    completion_digest: str | None = Field(default=None, sa_column=Column(String(64)))
    completion_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    error_code: str | None = Field(default=None, sa_column=Column(String(64)))


class MonitoringJobSelector(SQLModel, table=True):
    __tablename__ = "monitoring_job_selectors"
    __table_args__ = (
        ForeignKeyConstraint(
            ["selector_id", "version_id"],
            ["selector_versions.selector_id", "selector_versions.id"],
            name="fk_monitoring_selector_version_owner",
            ondelete="RESTRICT",
        ),
    )
    job_id: UUID = Field(sa_column=Column(Uuid, ForeignKey("monitoring_jobs.id"), primary_key=True))
    selector_id: int = Field(sa_column=reference("selectors.id", primary_key=True))
    version_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    fingerprint: str = Field(sa_column=Column(String(64), nullable=False))


class MonitoringUpload(SQLModel, table=True):
    __tablename__ = "monitoring_uploads"
    __table_args__ = (
        CheckConstraint("content_size > 0", name="monitoring_upload_positive_size"),
        UniqueConstraint("job_id", "lease_id", name="uq_monitoring_upload_per_attempt"),
        Index("ix_monitoring_uploads_cleanup", "expires_at", "cleaned_at"),
    )
    id: UUID = Field(default_factory=uuid4, sa_column=Column(Uuid, primary_key=True))
    job_id: UUID = Field(sa_column=Column(Uuid, ForeignKey("monitoring_jobs.id"), nullable=False))
    lease_id: UUID = Field(sa_column=Column(Uuid, nullable=False))
    storage_key: str = Field(sa_column=Column(Text, nullable=False, unique=True))
    content_hash: str = Field(sa_column=Column(String(64), nullable=False))
    content_size: int = Field(sa_column=Column(BigInteger, nullable=False))
    expires_at: datetime = Field(sa_column=timestamp())
    sealed_key: str | None = Field(default=None, sa_column=Column(Text))
    cleaned_at: datetime | None = Field(default=None, sa_column=timestamp(nullable=True))


class SourceCheckRun(SQLModel, table=True):
    """Check-specific history. The joined job holds lifecycle and snapshot references."""

    __tablename__ = "source_check_runs"
    job_id: UUID = Field(sa_column=Column(Uuid, ForeignKey("monitoring_jobs.id"), primary_key=True))
    scheduling_flow_run_id: str | None = Field(default=None, sa_column=Column(String(64)))
    processing_flow_run_id: str | None = Field(default=None, sa_column=Column(String(64)))
    acquired_at: datetime | None = Field(default=None, sa_column=timestamp(nullable=True))
    processed_at: datetime | None = Field(default=None, sa_column=timestamp(nullable=True))
    change_status: str | None = Field(default=None, sa_column=Column(String(32)))
    field_results: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSONB))


class OnboardingRun(SQLModel, table=True):
    __tablename__ = "monitoring_onboarding_runs"
    __table_args__ = (
        Index(
            "uq_monitoring_onboarding_continuous_policy",
            "policy_name",
            unique=True,
            postgresql_where=text("continuous"),
        ),
        Index(
            "ix_monitoring_onboarding_run_service",
            text("coalesce(last_serviced_at, created_at)"),
            "created_at",
            "id",
        ),
    )

    id: UUID = Field(default_factory=uuid4, sa_column=Column(Uuid, primary_key=True))
    policy_name: str = Field(sa_column=Column(String(48), nullable=False))
    criteria: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    continuous: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))
    after_source_id: int = Field(default=0, sa_column=Column(BigInteger, nullable=False))
    through_source_id: int | None = Field(default=None, sa_column=Column(BigInteger))
    scan_complete: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp())
    last_serviced_at: datetime | None = Field(default=None, sa_column=timestamp(nullable=True))


class OnboardingItem(SQLModel, table=True):
    __tablename__ = "monitoring_onboarding_items"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="onboarding_attempts_nonnegative"),
        Index(
            "ix_monitoring_onboarding_items_pending",
            "run_id",
            "available_at",
            "source_id",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    run_id: UUID = Field(
        sa_column=Column(
            Uuid,
            ForeignKey("monitoring_onboarding_runs.id", ondelete="CASCADE"),
            primary_key=True,
        )
    )
    source_id: int = Field(sa_column=reference("sources.id", primary_key=True))
    status: str = Field(default="pending", sa_column=Column(String(24), nullable=False))
    attempts: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    available_at: datetime = Field(default_factory=utc_now, sa_column=timestamp())
    source_state_at: datetime | None = Field(default=None, sa_column=timestamp(nullable=True))
    diagnostics: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=False)
    )


class DiscoveryOrigin(SQLModel, table=True):
    __tablename__ = "monitoring_discovery_origins"

    origin: str = Field(sa_column=Column(String(260), primary_key=True))
    next_request_at: datetime = Field(sa_column=timestamp())
