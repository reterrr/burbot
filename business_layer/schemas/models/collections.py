"""Universal, ordered collection identities and bitemporal item decisions."""

from datetime import datetime
from typing import Any

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
    UniqueConstraint,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, ExcludeConstraint
from sqlmodel import Field, SQLModel

from business_layer.schemas.models.data import created_at_column, utc_now
from sources.schemas.models import Source  # noqa: F401 -- registers the Source FK target


class BusinessCollection(SQLModel, table=True):
    __tablename__ = "business_collections"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(root_field_id, parent_item_id) = 1", name="business_collections_one_owner"
        ),
        CheckConstraint("revision >= 0", name="business_collections_revision"),
        UniqueConstraint("parent_item_id", name="uq_business_collections_parent_item"),
        UniqueConstraint("root_field_id", "id", name="uq_business_collections_root_identity"),
        Index("ix_business_collections_root_field", "root_field_id"),
    )
    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    root_field_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("business_object_fields.id", ondelete="RESTRICT")),
    )
    parent_item_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey(
                "business_collection_items.id",
                ondelete="RESTRICT",
                use_alter=True,
                name="fk_business_collections_parent_item",
            ),
        ),
    )
    revision: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, server_default=text("0"))
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessCollectionItem(SQLModel, table=True):
    __tablename__ = "business_collection_items"
    __table_args__ = (
        UniqueConstraint("id", "collection_id", name="uq_business_collection_items_owner"),
        Index("ix_business_collection_items_collection", "collection_id"),
    )
    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    collection_id: int = Field(
        sa_column=Column(
            BigInteger, ForeignKey("business_collections.id", ondelete="RESTRICT"), nullable=False
        )
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())


class BusinessCollectionItemVersion(SQLModel, table=True):
    __tablename__ = "business_collection_item_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["item_id", "collection_id"],
            ["business_collection_items.id", "business_collection_items.collection_id"],
            ondelete="RESTRICT",
            name="fk_business_collection_versions_item_owner",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="business_collection_versions_valid_range",
        ),
        CheckConstraint(
            "transaction_to IS NULL OR transaction_to > transaction_from",
            name="business_collection_versions_transaction_range",
        ),
        CheckConstraint(
            "(present AND position >= 0 AND position IS NOT NULL AND "
            "num_nonnulls(value_json, reference_object_id, source_id) = 1 AND "
            "(value_json IS NULL OR value_json <> 'null'::jsonb)) OR "
            "(NOT present AND position IS NULL AND "
            "num_nonnulls(value_json, reference_object_id, source_id) = 0)",
            name="business_collection_versions_value_channel",
        ),
        ExcludeConstraint(
            ("item_id", "="),
            (literal_column("tstzrange(valid_from, valid_to, '[)')"), "&&"),
            (literal_column("tstzrange(transaction_from, transaction_to, '[)')"), "&&"),
            using="gist",
            name="ex_business_collection_versions_item_overlap",
        ),
        # Owner identity is duplicated, with a composite FK, to enforce positions
        # across items. Deferred checking permits an atomic multi-item permutation.
        ExcludeConstraint(
            ("collection_id", "="),
            ("position", "="),
            (literal_column("tstzrange(valid_from, valid_to, '[)')"), "&&"),
            (literal_column("tstzrange(transaction_from, transaction_to, '[)')"), "&&"),
            where=text("present"),
            using="gist",
            deferrable=True,
            initially="DEFERRED",
            name="ex_business_collection_versions_position_overlap",
        ),
        Index("ix_business_collection_versions_item", "item_id"),
        Index("ix_business_collection_versions_collection", "collection_id"),
        Index("ix_business_collection_versions_recorded", "collection_id", "transaction_from"),
        Index("ix_business_collection_versions_reference", "reference_object_id"),
        Index("ix_business_collection_versions_source", "source_id"),
    )
    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    item_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    collection_id: int = Field(sa_column=Column(BigInteger, nullable=False))
    position: int | None = Field(default=None, sa_column=Column(Integer))
    value_json: Any | None = Field(default=None, sa_column=Column(JSONB(none_as_null=True)))
    reference_object_id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, ForeignKey("business_objects.id", ondelete="RESTRICT")),
    )
    source_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, ForeignKey("sources.id", ondelete="RESTRICT"))
    )
    present: bool = Field(sa_column=Column(Boolean, nullable=False))
    valid_from: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    valid_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    transaction_from: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    transaction_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())
