from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
    literal_column,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint, JSONB
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


def transaction_from_column() -> Column:
    return Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


def created_at_column() -> Column:
    return Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


# ============================================================
# BUSINESS OBJECT
# ============================================================


class BusinessObject(SQLModel, table=True):
    """
    Stable identity of one concrete BusinessEntity instance.

    BusinessEntity:
        Project

    BusinessObject:
        one concrete Project
    """

    __tablename__ = "business_objects"

    __table_args__ = (
        Index(
            "ix_business_objects_entity",
            "business_entity_id",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
    )

    business_entity_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("business_entities.id"),
            nullable=False,
        ),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=created_at_column(),
    )


# ============================================================
# BUSINESS OBJECT FIELD
# ============================================================


class BusinessObjectField(SQLModel, table=True):
    """
    Stable identity of one object + field slot.

    Example:

        BusinessObject #5001
            Project

        BusinessEntityField #123
            budget

        BusinessObjectField #9001
            Project #5001.budget

    Values of this slot live in BusinessObjectFieldValue.
    """

    __tablename__ = "business_object_fields"

    __table_args__ = (
        UniqueConstraint(
            "business_object_id",
            "business_entity_field_id",
            name="uq_business_object_fields_object_entity_field",
        ),
        Index(
            "ix_business_object_fields_object",
            "business_object_id",
        ),
        Index(
            "ix_business_object_fields_entity_field",
            "business_entity_field_id",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
    )

    business_object_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("business_objects.id"),
            nullable=False,
        ),
    )

    business_entity_field_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("business_entity_fields.id"),
            nullable=False,
        ),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=created_at_column(),
    )


# ============================================================
# BUSINESS OBJECT FIELD VALUE
# ============================================================


class BusinessObjectFieldValue(SQLModel, table=True):
    """
    Canonical bitemporal value of one BusinessObjectField.

    This is NOT raw extracted data.

    Example:

        BusinessObjectField #9001
            Project #5001.budget

        BusinessObjectFieldValue
            value_json = 125000

    Extraction provenance is handled separately through:

        FieldObservation
            ->
        BusinessObjectFieldValueEvidence
            ->
        BusinessObjectFieldValue
    """

    __tablename__ = "business_object_field_values"

    __table_args__ = (
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="business_object_field_values_valid_range",
        ),
        CheckConstraint(
            """
            transaction_to IS NULL
            OR transaction_to > transaction_from
            """,
            name="business_object_field_values_transaction_range",
        ),

        # Prevent two ambiguous canonical values for the same
        # BusinessObjectField at the same valid-time AND
        # transaction-time point.
        #
        # Requires PostgreSQL extension:
        #
        #   CREATE EXTENSION IF NOT EXISTS btree_gist;
        #
        ExcludeConstraint(
            (
                "business_object_field_id",
                "=",
            ),
            (
                literal_column(
                    "tstzrange(valid_from, valid_to, '[)')"
                ),
                "&&",
            ),
            (
                literal_column(
                    "tstzrange("
                    "transaction_from, "
                    "transaction_to, "
                    "'[)'"
                    ")"
                ),
                "&&",
            ),
            using="gist",
            name="ex_business_object_field_values_bitemporal_overlap",
        ),

        Index(
            "ix_business_object_field_values_field",
            "business_object_field_id",
        ),
        Index(
            "ix_business_object_field_values_field_valid_from",
            "business_object_field_id",
            "valid_from",
        ),
        Index(
            "ix_business_object_field_values_field_valid_to",
            "business_object_field_id",
            "valid_to",
        ),
        Index(
            "ix_business_object_field_values_field_transaction_from",
            "business_object_field_id",
            "transaction_from",
        ),
        Index(
            "ix_business_object_field_values_field_transaction_to",
            "business_object_field_id",
            "transaction_to",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            primary_key=True,
            autoincrement=True,
        ),
    )

    business_object_field_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("business_object_fields.id"),
            nullable=False,
        ),
    )

    # Intentionally Any.
    #
    # JSONB is only the physical carrier.
    # The corresponding BusinessEntityFieldVersion.definition_json
    # determines the logical type.
    #
    # Examples:
    #
    #   "Hello"
    #   125000
    #   12.5
    #   true
    #   ["A", "B"]
    #   {"currency": "PLN", "amount": 125000}
    #
    value_json: Any = Field(
        sa_column=Column(
            JSONB,
            nullable=False,
        ),
    )

    # --------------------------------------------------------
    # VALID TIME
    # --------------------------------------------------------
    #
    # When the value is true in the modeled business world.
    #

    valid_from: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
        ),
    )

    valid_to: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )

    # --------------------------------------------------------
    # TRANSACTION TIME
    # --------------------------------------------------------
    #
    # When Burbot believed/stored this version.
    #

    transaction_from: datetime = Field(
        default_factory=utc_now,
        sa_column=transaction_from_column(),
    )

    transaction_to: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=created_at_column(),
    )
