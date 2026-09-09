"""Source registry tables; no imports from the business or extraction modules."""

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

from sources.schemas.common import CreatedAtMixin, UpdatedAtMixin, pg_enum, utc_now
from sources.schemas.enums import SourceState, SourceStateTrigger, SourceType


class StoredFile(CreatedAtMixin, table=True):
    """Describe a payload stored outside the relational database.

    :ivar id: Database primary key.
    :ivar storage_key: Storage key.
    :ivar original_name: Original name.
    :ivar mime_type: Mime type.
    :ivar size_bytes: Size bytes.
    :ivar sha256: Sha256.
    :ivar purged_at: Timestamp for purged.
    """

    __tablename__ = "stored_files"
    __table_args__ = (
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="size_bytes_non_negative",
        ),
        Index("ix_stored_files_sha256", "sha256"),
    )

    id: int | None = Field(default=None, primary_key=True)
    storage_key: str = Field(sa_column=Column(String, nullable=False, unique=True))
    original_name: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    mime_type: str = Field(sa_column=Column(String, nullable=False))
    size_bytes: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, nullable=True),
    )
    sha256: str | None = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )
    purged_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class Source(UpdatedAtMixin, table=True):
    """Register an HTML or PDF URL with an optional stored payload reference.

    :ivar id: Database primary key.
    :ivar url: Canonical URL of the sources.
    :ivar state: State.
    :ivar source_type: Source type.
    :ivar file_id: Identifier of the related file.
    :ivar last_state_change_at: Timestamp for last state change.
    """

    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("url", name="uq_sources_url"),
        Index("ix_sources_state", "state"),
        Index("ix_sources_source_type", "source_type"),
    )

    id: int | None = Field(default=None, primary_key=True)
    url: str = Field(sa_column=Column(Text, nullable=False))
    state: SourceState = Field(
        default=SourceState.UNDISCOVERED,
        sa_column=Column(
            pg_enum(SourceState, "source_state"),
            nullable=False,
            server_default=text("'UNDISCOVERED'"),
        ),
    )
    source_type: SourceType = Field(
        sa_column=Column(pg_enum(SourceType, "source_type"), nullable=False)
    )
    file_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("stored_files.id", ondelete="RESTRICT"),
            nullable=True,
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


class SourceStateHistory(SQLModel, table=True):
    """Record an immutable sources state transition.

    :ivar id: Database primary key.
    :ivar source_id: Identifier of the related sources.
    :ivar from_state: From state.
    :ivar to_state: To state.
    :ivar changed_at: Timestamp for changed.
    :ivar reason: Reason.
    :ivar triggered_by: Triggered by.
    """

    __tablename__ = "source_state_history"
    __table_args__ = (
        Index(
            "ix_source_state_history_source_changed",
            "source_id",
            "changed_at",
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
    from_state: SourceState | None = Field(
        default=None,
        sa_column=Column(pg_enum(SourceState, "source_state"), nullable=True),
    )
    to_state: SourceState = Field(
        sa_column=Column(pg_enum(SourceState, "source_state"), nullable=False)
    )
    changed_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        )
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
