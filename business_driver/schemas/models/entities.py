from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from business_driver.schemas.enums import (
    BusinessEntityFieldCardinality,
    BusinessEntityFieldDataType,
    ConfirmedBy,
)


def utc_now() -> datetime:
    """Return an aware UTC timestamp without depending on the host project."""  
    return datetime.now(timezone.utc)


class BusinessEntity(SQLModel, table=True):
    """Generic identity of something Burbot tracks as a business entity."""

    __tablename__ = "business_entities"

    id: int | None = Field(default=None, primary_key=True)
    entity_type: str = Field(
        sa_column=Column(String(100), nullable=False, index=True),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


class BusinessEntityRelation(SQLModel, table=True):
    """Directed, versionable relation between two business entities."""

    __tablename__ = "business_entity_relations"
    __table_args__ = (
        UniqueConstraint(
            "from_entity_id",
            "to_entity_id",
            "relation_key",
            "valid_from",
            name="uq_business_entity_relation_version",
        ),
        Index(
            "ix_business_entity_relations_from_entity_id",
            "from_entity_id",
        ),
        Index(
            "ix_business_entity_relations_to_entity_id",
            "to_entity_id",
        ),
        Index(
            "ix_business_entity_relations_current",
            "from_entity_id",
            "to_entity_id",
            "relation_key",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    from_entity_id: int = Field(
        foreign_key="business_entities.id",
        nullable=False,
    )
    to_entity_id: int = Field(
        foreign_key="business_entities.id",
        nullable=False,
    )

    relation_key: str = Field(
        sa_column=Column(String(150), nullable=False),
    )
    metadata_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )

    valid_from: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    valid_to: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class BusinessEntityRevision(SQLModel, table=True):
    """Groups several accepted field changes into one logical update."""

    __tablename__ = "business_entity_revisions"

    id: int | None = Field(default=None, primary_key=True)
    business_entity_id: int = Field(
        foreign_key="business_entities.id",
        nullable=False,
        index=True,
    )

    reason: str | None = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    metadata_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class BusinessEntityField(SQLModel, table=True):
    """Definition of a field belonging to one concrete business entity."""

    __tablename__ = "business_entity_fields"
    __table_args__ = (
        Index(
            "uq_business_entity_fields_active_key",
            "business_entity_id",
            "key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    business_entity_id: int = Field(
        foreign_key="business_entities.id",
        nullable=False,
        index=True,
    )

    key: str = Field(
        sa_column=Column(String(150), nullable=False),
    )
    label: str = Field(
        sa_column=Column(String(255), nullable=False),
    )
    data_type: BusinessEntityFieldDataType = Field(
        sa_column=Column(
            Enum(
                BusinessEntityFieldDataType,
                name="business_entity_field_data_type",
            ),
            nullable=False,
        ),
    )
    cardinality: BusinessEntityFieldCardinality = Field(
        default=BusinessEntityFieldCardinality.ONE,
        sa_column=Column(
            Enum(
                BusinessEntityFieldCardinality,
                name="business_entity_field_cardinality",
            ),
            nullable=False,
            server_default=BusinessEntityFieldCardinality.ONE.value,
        ),
    )

    required: bool = Field(default=False, nullable=False)
    description: str | None = Field(default=None)

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class BusinessEntityFieldValue(SQLModel, table=True):
    """One version of the accepted business value for an entity field.

    Current value = ``valid_to IS NULL``. There is at most one current row per
    field. For cardinality=MANY, ``value_json`` contains a JSON array rather
    than creating several simultaneous current rows. This keeps current-state
    semantics simple and lets PostgreSQL enforce the invariant directly.
    """

    __tablename__ = "business_entity_field_values"
    __table_args__ = (
        Index(
            "ix_business_entity_field_values_field_valid_to",
            "business_entity_field_id",
            "valid_to",
        ),
        Index(
            "ix_business_entity_field_values_revision_id",
            "revision_id",
        ),
        Index(
            "uq_business_entity_field_values_current",
            "business_entity_field_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    business_entity_field_id: int = Field(
        foreign_key="business_entity_fields.id",
        nullable=False,
        index=True,
    )
    revision_id: int | None = Field(
        default=None,
        foreign_key="business_entity_revisions.id",
        nullable=True,
    )

    value_json: Any = Field(
        sa_column=Column(JSONB, nullable=False),
    )

    confirmed_by: ConfirmedBy = Field(
        sa_column=Column(
            Enum(
                ConfirmedBy,
                name="business_entity_field_value_confirmed_by",
            ),
            nullable=False,
        ),
    )

    valid_from: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    valid_to: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
