from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    literal_column,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlmodel import Field, SQLModel

from business_layer.schemas.enums import BusinessDefinitionStatus, BusinessRelationCardinality


def utc_now() -> datetime:
    return datetime.now(UTC)


def pg_enum(enum_class: type[StrEnum], name: str) -> SAEnum:
    return SAEnum(
        enum_class,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda members: [str(member.value) for member in members],
    )


def created_at_column() -> Column:
    return Column(DateTime(timezone=True), nullable=False, server_default=func.now())


def transaction_from_column() -> Column:
    return Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class BusinessModel(SQLModel, table=True):
    """Top-level logical namespace for business schemas."""

    __tablename__ = "business_models"
    __table_args__ = (
        UniqueConstraint("key", name="uq_business_models_key"),
        # The selected revision must belong to this business model.
        ForeignKeyConstraint(
            ["id", "current_revision_id"],
            ["business_model_revisions.business_model_id", "business_model_revisions.id"],
            name="fk_business_models_current_revision_own",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    key: str = Field(sa_column=Column(String(150), nullable=False))
    name: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    current_revision_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, nullable=True),
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessModelRevision(SQLModel, table=True):
    """One logical schemas commit grouping definition changes."""

    __tablename__ = "business_model_revisions"
    __table_args__ = (
        Index("ix_business_model_revisions_model", "business_model_id"),
        Index("ix_business_model_revisions_model_created", "business_model_id", "created_at"),
        UniqueConstraint("business_model_id", "id", name="uq_business_model_revisions_model_id"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_model_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("business_models.id", ondelete="RESTRICT", name="fk_business_model_revisions_model"), nullable=False)
    )
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessEntity(SQLModel, table=True):
    """Stable identity of a logical entity type, similar to a table."""

    __tablename__ = "business_entities"
    __table_args__ = (
        Index("ix_business_entities_model", "business_model_id"),
        UniqueConstraint("id", "business_model_id", name="uq_business_entity_model_owner"),
        UniqueConstraint("business_model_id", "table_name", name="uq_business_entities_model_table_name"),
        UniqueConstraint("business_model_id", "physical_name", name="uq_business_entities_model_physical_name"),
        # Prevent a pointer to a version of a different entity.
        ForeignKeyConstraint(
            ["id", "effective_business_entity_version_id"],
            ["business_entity_versions.business_entity_id", "business_entity_versions.id"],
            name="fk_business_entities_effective_version_own",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_model_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("business_models.id", ondelete="RESTRICT"), nullable=False)
    )
    physical_name: str | None = Field(default=None, sa_column=Column(String(150), nullable=True))
    table_name: str = Field(sa_column=Column(String(54), nullable=False))  # stable identifier
    effective_business_entity_version_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, nullable=True),
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessEntityVersion(SQLModel, table=True):
    """Bitemporal definition of a BusinessEntity."""

    __tablename__ = "business_entity_versions"
    __table_args__ = (
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="business_entity_versions_valid_range"),
        CheckConstraint("transaction_to IS NULL OR transaction_to > transaction_from",
                        name="business_entity_versions_transaction_range"),
        ExcludeConstraint(
            ("business_entity_id", "="),
            (literal_column("tstzrange(valid_from, valid_to, '[)')"), "&&"),
            (literal_column("tstzrange(transaction_from, transaction_to, '[)')"), "&&"),
            using="gist",
            name="ex_business_entity_versions_bitemporal_overlap",
        ),
        UniqueConstraint("business_entity_id", "id", name="uq_business_entity_versions_entity_id"),
        Index("ix_business_entity_versions_entity", "business_entity_id"),
        Index("ix_business_entity_versions_revision", "business_model_revision_id"),
        Index("ix_business_entity_versions_entity_valid_from", "business_entity_id", "valid_from"),
        Index("ix_business_entity_versions_entity_transaction_from", "business_entity_id", "transaction_from"),
        Index("ix_business_entity_versions_entity_valid_to", "business_entity_id", "valid_to"),
        Index("ix_business_entity_versions_entity_transaction_to", "business_entity_id", "transaction_to"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_entity_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("business_entities.id", ondelete="RESTRICT"), nullable=False))
    business_model_revision_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("business_model_revisions.id", ondelete="RESTRICT"), nullable=False))
    key: str = Field(sa_column=Column(String(150), nullable=False))
    label: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: BusinessDefinitionStatus = Field(
        default=BusinessDefinitionStatus.ACTIVE,
        sa_column=Column(pg_enum(BusinessDefinitionStatus, "business_definition_status"), nullable=False,
                         server_default=BusinessDefinitionStatus.ACTIVE.value),
    )
    definition_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    valid_from: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    valid_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    transaction_from: datetime = Field(default_factory=utc_now, sa_column=transaction_from_column())
    transaction_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessEntityField(SQLModel, table=True):
    """Stable identity of one logical field belonging to a BusinessEntity."""

    __tablename__ = "business_entity_fields"
    __table_args__ = (
        Index("ix_business_entity_fields_entity", "business_entity_id"),
        UniqueConstraint("business_entity_id", "persistent_key", name="uq_business_entity_fields_entity_persistent_key"),
        CheckConstraint("persistent_key <> '' AND persistent_key = trim(persistent_key)",
                        name="business_entity_fields_persistent_key_valid"),
        # Supports composite FKs ensuring relation endpoints use fields of the right entity.
        UniqueConstraint("business_entity_id", "id", name="uq_business_entity_fields_entity_id"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_entity_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("business_entities.id", ondelete="RESTRICT"), nullable=False))
    persistent_key: str = Field(sa_column=Column(String(150), nullable=False))
    physical_name: str | None = Field(default=None, sa_column=Column(String(150), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessEntityFieldVersion(SQLModel, table=True):
    """Bitemporal field definition; logical type and constraints live in definition_json."""

    __tablename__ = "business_entity_field_versions"
    __table_args__ = (
        UniqueConstraint(
            "id", "business_entity_field_id", name="uq_business_field_versions_field_owner"
        ),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="business_entity_field_versions_valid_range"),
        CheckConstraint("transaction_to IS NULL OR transaction_to > transaction_from",
                        name="business_entity_field_versions_transaction_range"),
        ExcludeConstraint(
            ("business_entity_field_id", "="),
            (literal_column("tstzrange(valid_from, valid_to, '[)')"), "&&"),
            (literal_column("tstzrange(transaction_from, transaction_to, '[)')"), "&&"),
            using="gist",
            name="ex_business_entity_field_versions_bitemporal_overlap",
        ),
        Index("ix_business_entity_field_versions_field", "business_entity_field_id"),
        Index("ix_business_entity_field_versions_revision", "business_model_revision_id"),
        Index("ix_business_entity_field_versions_field_valid_from", "business_entity_field_id", "valid_from"),
        Index("ix_business_entity_field_versions_field_transaction_from", "business_entity_field_id",
              "transaction_from"),
        Index("ix_business_entity_field_versions_field_valid_to", "business_entity_field_id", "valid_to"),
        Index("ix_business_entity_field_versions_field_transaction_to", "business_entity_field_id", "transaction_to"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_entity_field_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("business_entity_fields.id", ondelete="RESTRICT"), nullable=False))
    business_model_revision_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("business_model_revisions.id", ondelete="RESTRICT"), nullable=False))
    key: str = Field(sa_column=Column(String(150), nullable=False))
    label: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: BusinessDefinitionStatus = Field(
        default=BusinessDefinitionStatus.ACTIVE,
        sa_column=Column(pg_enum(BusinessDefinitionStatus, "business_definition_status"), nullable=False,
                         server_default=BusinessDefinitionStatus.ACTIVE.value),
    )
    definition_json: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
    valid_from: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    valid_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    transaction_from: datetime = Field(default_factory=utc_now, sa_column=transaction_from_column())
    transaction_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessEntityRelationVersion(SQLModel, table=True):
    """Bitemporal relation definition; no separate relation-identity table.

    ``id`` identifies one historical record. All historical records of the same
    logical relation share ``relation_id`` (UUID), even when its key changes.

    Endpoints reference stable entity and field identities, never their specific
    bitemporal version rows. At any (valid_time, transaction_time), resolve
    the applicable versions by querying their independent histories.
    """

    __tablename__ = "business_entity_relation_versions"
    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="business_entity_relation_versions_valid_range",
        ),
        CheckConstraint(
            "transaction_to IS NULL OR transaction_to > transaction_from",
            name="business_entity_relation_versions_transaction_range",
        ),
        # A logical relation cannot have two competing versions for the same
        # valid time AND transaction time. Requires PostgreSQL btree_gist.
        ExcludeConstraint(
            ("relation_id", "="),
            (literal_column("tstzrange(valid_from, valid_to, '[)')"), "&&"),
            (literal_column("tstzrange(transaction_from, transaction_to, '[)')"), "&&"),
            using="gist",
            name="ex_business_entity_relation_versions_bitemporal_overlap",
        ),
        Index("ix_business_entity_relation_versions_relation", "relation_id"),
        Index("ix_business_entity_relation_versions_revision", "business_model_revision_id"),
        Index("ix_business_entity_relation_versions_from_entity", "from_entity_id"),
        Index("ix_business_entity_relation_versions_to_entity", "to_entity_id"),
        Index("ix_business_entity_relation_versions_from_field", "from_field_id"),
        Index("ix_business_entity_relation_versions_to_field", "to_field_id"),
        # A relation may point only to a field belonging to its endpoint entity.
        # For nullable field IDs, PostgreSQL's default MATCH SIMPLE permits
        # entity-level relations with no field endpoint.
        ForeignKeyConstraint(
            ["from_entity_id", "from_field_id"],
            ["business_entity_fields.business_entity_id", "business_entity_fields.id"],
            ondelete="RESTRICT",
            name="fk_relation_versions_from_field_own",
        ),
        ForeignKeyConstraint(
            ["to_entity_id", "to_field_id"],
            ["business_entity_fields.business_entity_id", "business_entity_fields.id"],
            ondelete="RESTRICT",
            name="fk_relation_versions_to_field_own",
        ),
        Index("ix_business_entity_relation_versions_relation_valid_from", "relation_id", "valid_from"),
        Index("ix_business_entity_relation_versions_relation_transaction_from", "relation_id", "transaction_from"),
        Index("ix_business_entity_relation_versions_relation_valid_to", "relation_id", "valid_to"),
        Index("ix_business_entity_relation_versions_relation_transaction_to", "relation_id", "transaction_to"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
    )
    relation_id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(Uuid(as_uuid=True), nullable=False),
    )
    business_model_revision_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("business_model_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    key: str = Field(sa_column=Column(String(150), nullable=False))
    label: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    from_entity_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("business_entities.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    to_entity_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("business_entities.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    # Composite foreign keys above enforce that each optional field belongs
    # to the corresponding endpoint entity.
    from_field_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    to_field_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    cardinality: BusinessRelationCardinality = Field(
        sa_column=Column(
            pg_enum(BusinessRelationCardinality, "business_relation_cardinality"),
            nullable=False,
        )
    )
    status: BusinessDefinitionStatus = Field(
        default=BusinessDefinitionStatus.ACTIVE,
        sa_column=Column(
            pg_enum(BusinessDefinitionStatus, "business_definition_status"),
            nullable=False,
            server_default=BusinessDefinitionStatus.ACTIVE.value,
        ),
    )
    definition_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )
    valid_from: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    valid_to: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    transaction_from: datetime = Field(
        default_factory=utc_now,
        sa_column=transaction_from_column(),
    )
    transaction_to: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())
