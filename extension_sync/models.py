"""Durable namespace, external identities and idempotent operation receipts."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from extraction.schemas.common import utc_now


class SyncWorkspace(SQLModel, table=True):
    __tablename__ = "extension_sync_workspaces"
    __table_args__ = (UniqueConstraint("id", "business_model_id", name="uq_sync_workspace_model"),)

    id: UUID = Field(sa_column=Column(Uuid, primary_key=True))
    business_model_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("business_models.id"),
            nullable=False,
        )
    )
    token_digest: str = Field(sa_column=Column(String(64), nullable=False, unique=True))
    enabled: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))
    can_create: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))
    can_bind_existing: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))
    can_commit: bool = Field(default=False, sa_column=Column(Boolean, nullable=False))
    source_policy: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class SyncSourceGrant(SQLModel, table=True):
    __tablename__ = "extension_sync_source_grants"
    workspace_id: UUID = Field(
        sa_column=Column(
            Uuid,
            ForeignKey("extension_sync_workspaces.id"),
            primary_key=True,
        )
    )
    source_id: int = Field(sa_column=Column(BigInteger, ForeignKey("sources.id"), primary_key=True))


class ExternalObjectBinding(SQLModel, table=True):
    __tablename__ = "extension_sync_object_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "business_model_id"],
            ["extension_sync_workspaces.id", "extension_sync_workspaces.business_model_id"],
            name="fk_sync_object_workspace_model",
        ),
        ForeignKeyConstraint(
            ["business_entity_id", "business_model_id"],
            ["business_entities.id", "business_entities.business_model_id"],
            name="fk_sync_object_entity_model",
        ),
        ForeignKeyConstraint(
            ["business_object_id", "business_entity_id"],
            ["business_objects.id", "business_objects.business_entity_id"],
            name="fk_sync_object_object_entity",
        ),
        UniqueConstraint("workspace_id", "business_object_id", name="uq_sync_workspace_object"),
    )
    workspace_id: UUID = Field(sa_column=Column(Uuid, primary_key=True))
    external_object_id: str = Field(sa_column=Column(Text, primary_key=True))
    business_model_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    business_entity_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    business_object_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class SyncReceipt(SQLModel, table=True):
    __tablename__ = "extension_sync_receipts"
    workspace_id: UUID = Field(
        sa_column=Column(
            Uuid,
            ForeignKey("extension_sync_workspaces.id"),
            primary_key=True,
        )
    )
    operation_id: UUID = Field(sa_column=Column(Uuid, primary_key=True))
    digest: str = Field(sa_column=Column(String(64), nullable=False))
    result: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
