from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Enum as SAEnum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlmodel import Field, SQLModel

from business_driver.schemas.enums import BusinessDefinitionStatus, BusinessRelationCardinality


def utc_now() -> datetime:
    return datetime.now(UTC)


def pg_enum(enum_class: type, name: str) -> SAEnum:
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
    """Top-level logical namespace for a business schema."""

    __tablename__ = "business_models"
    __table_args__ = (UniqueConstraint("key", name="uq_business_models_key"),)

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    key: str = Field(sa_column=Column(String(150), nullable=False))
    name: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessModelRevision(SQLModel, table=True):
    """One logical schema commit grouping definition changes."""

    __tablename__ = "business_model_revisions"
    __table_args__ = (
        Index("ix_business_model_revisions_model", "business_model_id"),
        Index("ix_business_model_revisions_model_created", "business_model_id", "created_at"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_model_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_models.id", ondelete="RESTRICT"), nullable=False))
    reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    metadata_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessEntity(SQLModel, table=True):
    """Stable identity of a logical entity type, similar to a table."""

    __tablename__ = "business_entities"
    __table_args__ = (
        Index("ix_business_entities_model", "business_model_id"),
        UniqueConstraint("business_model_id", "physical_name", name="uq_business_entities_model_physical_name"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_model_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_models.id", ondelete="RESTRICT"), nullable=False))
    physical_name: str | None = Field(default=None, sa_column=Column(String(150), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessEntityVersion(SQLModel, table=True):
    """Bitemporal definition of a BusinessEntity."""

    __tablename__ = "business_entity_versions"
    __table_args__ = (
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="business_entity_versions_valid_range"),
        CheckConstraint("transaction_to IS NULL OR transaction_to > transaction_from", name="business_entity_versions_transaction_range"),
        ExcludeConstraint(
            ("business_entity_id", "="),
            (func.tstzrange("valid_from", "valid_to", "[)"), "&&"),
            (func.tstzrange("transaction_from", "transaction_to", "[)"), "&&"),
            using="gist",
            name="ex_business_entity_versions_bitemporal_overlap",
        ),
        Index("ix_business_entity_versions_entity", "business_entity_id"),
        Index("ix_business_entity_versions_revision", "revision_id"),
        Index("ix_business_entity_versions_entity_valid_from", "business_entity_id", "valid_from"),
        Index("ix_business_entity_versions_entity_transaction_from", "business_entity_id", "transaction_from"),
        Index("ix_business_entity_versions_entity_valid_to", "business_entity_id", "valid_to"),
        Index("ix_business_entity_versions_entity_transaction_to", "business_entity_id", "transaction_to"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_entity_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_entities.id", ondelete="RESTRICT"), nullable=False))
    revision_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_model_revisions.id", ondelete="RESTRICT"), nullable=False))
    key: str = Field(sa_column=Column(String(150), nullable=False))
    label: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: BusinessDefinitionStatus = Field(
        default=BusinessDefinitionStatus.ACTIVE,
        sa_column=Column(pg_enum(BusinessDefinitionStatus, "business_definition_status"), nullable=False, server_default=BusinessDefinitionStatus.ACTIVE.value),
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
        UniqueConstraint("business_entity_id", "physical_name", name="uq_business_entity_fields_entity_physical_name"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_entity_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_entities.id", ondelete="RESTRICT"), nullable=False))
    physical_name: str | None = Field(default=None, sa_column=Column(String(150), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessEntityFieldVersion(SQLModel, table=True):
    """Bitemporal field definition; logical type and constraints live in definition_json."""

    __tablename__ = "business_entity_field_versions"
    __table_args__ = (
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="business_entity_field_versions_valid_range"),
        CheckConstraint("transaction_to IS NULL OR transaction_to > transaction_from", name="business_entity_field_versions_transaction_range"),
        ExcludeConstraint(
            ("business_entity_field_id", "="),
            (func.tstzrange("valid_from", "valid_to", "[)"), "&&"),
            (func.tstzrange("transaction_from", "transaction_to", "[)"), "&&"),
            using="gist",
            name="ex_business_entity_field_versions_bitemporal_overlap",
        ),
        Index("ix_business_entity_field_versions_field", "business_entity_field_id"),
        Index("ix_business_entity_field_versions_revision", "revision_id"),
        Index("ix_business_entity_field_versions_field_valid_from", "business_entity_field_id", "valid_from"),
        Index("ix_business_entity_field_versions_field_transaction_from", "business_entity_field_id", "transaction_from"),
        Index("ix_business_entity_field_versions_field_valid_to", "business_entity_field_id", "valid_to"),
        Index("ix_business_entity_field_versions_field_transaction_to", "business_entity_field_id", "transaction_to"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_entity_field_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_entity_fields.id", ondelete="RESTRICT"), nullable=False))
    revision_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_model_revisions.id", ondelete="RESTRICT"), nullable=False))
    key: str = Field(sa_column=Column(String(150), nullable=False))
    label: str = Field(sa_column=Column(String(255), nullable=False))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    status: BusinessDefinitionStatus = Field(
        default=BusinessDefinitionStatus.ACTIVE,
        sa_column=Column(pg_enum(BusinessDefinitionStatus, "business_definition_status"), nullable=False, server_default=BusinessDefinitionStatus.ACTIVE.value),
    )
    definition_json: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
    valid_from: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    valid_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    transaction_from: datetime = Field(default_factory=utc_now, sa_column=transaction_from_column())
    transaction_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessEntityRelation(SQLModel, table=True):
    """Stable conceptual identity of one relation inside a BusinessModel."""

    __tablename__ = "business_entity_relations"
    __table_args__ = (Index("ix_business_entity_relations_model", "business_model_id"),)

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_model_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_models.id", ondelete="RESTRICT"), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessEntityRelationVersion(SQLModel, table=True):
    """Bitemporal relation definition including versioned endpoints and field bindings."""

    __tablename__ = "business_entity_relation_versions"
    __table_args__ = (
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="business_entity_relation_versions_valid_range"),
        CheckConstraint("transaction_to IS NULL OR transaction_to > transaction_from", name="business_entity_relation_versions_transaction_range"),
        ExcludeConstraint(
            ("business_entity_relation_id", "="),
            (func.tstzrange("valid_from", "valid_to", "[)"), "&&"),
            (func.tstzrange("transaction_from", "transaction_to", "[)"), "&&"),
            using="gist",
            name="ex_business_entity_relation_versions_bitemporal_overlap",
        ),
        Index("ix_business_entity_relation_versions_relation", "business_entity_relation_id"),
        Index("ix_business_entity_relation_versions_revision", "revision_id"),
        Index("ix_business_entity_relation_versions_from_entity", "from_entity_id"),
        Index("ix_business_entity_relation_versions_to_entity", "to_entity_id"),
        Index("ix_business_entity_relation_versions_from_field", "from_field_id"),
        Index("ix_business_entity_relation_versions_to_field", "to_field_id"),
        Index("ix_business_entity_relation_versions_relation_valid_from", "business_entity_relation_id", "valid_from"),
        Index("ix_business_entity_relation_versions_relation_transaction_from", "business_entity_relation_id", "transaction_from"),
        Index("ix_business_entity_relation_versions_relation_valid_to", "business_entity_relation_id", "valid_to"),
        Index("ix_business_entity_relation_versions_relation_transaction_to", "business_entity_relation_id", "transaction_to"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_entity_relation_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_entity_relations.id", ondelete="RESTRICT"), nullable=False))
    revision_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_model_revisions.id", ondelete="RESTRICT"), nullable=False))
    key: str = Field(sa_column=Column(String(150), nullable=False))
    label: str | None = Field(default=None, sa_column=Column(String(255), nullable=True))
    description: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    from_entity_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_entities.id", ondelete="RESTRICT"), nullable=False))
    to_entity_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_entities.id", ondelete="RESTRICT"), nullable=False))
    from_field_id: int | None = Field(default=None, sa_column=Column(BigInteger, ForeignKey("business_entity_fields.id", ondelete="RESTRICT"), nullable=True))
    to_field_id: int | None = Field(default=None, sa_column=Column(BigInteger, ForeignKey("business_entity_fields.id", ondelete="RESTRICT"), nullable=True))
    cardinality: BusinessRelationCardinality = Field(
        sa_column=Column(pg_enum(BusinessRelationCardinality, "business_relation_cardinality"), nullable=False)
    )
    status: BusinessDefinitionStatus = Field(
        default=BusinessDefinitionStatus.ACTIVE,
        sa_column=Column(pg_enum(BusinessDefinitionStatus, "business_definition_status"), nullable=False, server_default=BusinessDefinitionStatus.ACTIVE.value),
    )
    definition_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    valid_from: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    valid_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    transaction_from: datetime = Field(default_factory=utc_now, sa_column=transaction_from_column())
    transaction_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessObject(SQLModel, table=True):
    """Concrete instance of a BusinessEntity, similar to a row."""

    __tablename__ = "business_objects"
    __table_args__ = (Index("ix_business_objects_entity", "business_entity_id"),)

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_entity_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_entities.id", ondelete="RESTRICT"), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessObjectField(SQLModel, table=True):
    """Stable identity of one concrete object+field slot."""

    __tablename__ = "business_object_fields"
    __table_args__ = (
        UniqueConstraint("business_object_id", "business_entity_field_id", name="uq_business_object_fields_object_field"),
        Index("ix_business_object_fields_object", "business_object_id"),
        Index("ix_business_object_fields_entity_field", "business_entity_field_id"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_object_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_objects.id", ondelete="RESTRICT"), nullable=False))
    business_entity_field_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_entity_fields.id", ondelete="RESTRICT"), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessObjectFieldValue(SQLModel, table=True):
    """Bitemporal value history for one BusinessObjectField slot."""

    __tablename__ = "business_object_field_values"
    __table_args__ = (
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="business_object_field_values_valid_range"),
        CheckConstraint("transaction_to IS NULL OR transaction_to > transaction_from", name="business_object_field_values_transaction_range"),
        ExcludeConstraint(
            ("business_object_field_id", "="),
            (func.tstzrange("valid_from", "valid_to", "[)"), "&&"),
            (func.tstzrange("transaction_from", "transaction_to", "[)"), "&&"),
            using="gist",
            name="ex_business_object_field_values_bitemporal_overlap",
        ),
        Index("ix_business_object_field_values_object_field", "business_object_field_id"),
        Index("ix_business_object_field_values_object_field_valid_from", "business_object_field_id", "valid_from"),
        Index("ix_business_object_field_values_object_field_transaction_from", "business_object_field_id", "transaction_from"),
        Index("ix_business_object_field_values_object_field_valid_to", "business_object_field_id", "valid_to"),
        Index("ix_business_object_field_values_object_field_transaction_to", "business_object_field_id", "transaction_to"),
    )

    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True, autoincrement=True))
    business_object_field_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_object_fields.id", ondelete="RESTRICT"), nullable=False))
    value_json: Any = Field(sa_column=Column(JSONB, nullable=False))
    valid_from: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    valid_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    transaction_from: datetime = Field(default_factory=utc_now, sa_column=transaction_from_column())
    transaction_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())
