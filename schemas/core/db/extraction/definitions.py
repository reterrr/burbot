"""Low-level token types and business target-field definitions."""

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field

from ..enums import BusinessEntityType
from ..mixins import SoftDeleteMixin, pg_enum


class TokenClass(SoftDeleteMixin, table=True):
    __tablename__ = "token_classes"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String, nullable=False, unique=True))
    validation_regex: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    parser_name: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    description: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )


class TargetField(SoftDeleteMixin, table=True):
    __tablename__ = "target_fields"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "name",
            name="uq_target_fields_entity_name",
        ),
        Index("ix_target_fields_expected_type_id", "expected_type_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    entity_type: BusinessEntityType = Field(
        sa_column=Column(
            pg_enum(BusinessEntityType, "business_entity_type"),
            nullable=False,
        )
    )
    name: str = Field(sa_column=Column(String, nullable=False))
    expected_type_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("token_classes.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    validation_regex: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    description: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    required: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
