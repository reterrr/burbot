"""Generalized sequential/associative patterns and runtime matches."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field

from ..enums import (
    DiscoveryMethod,
    ItemKind,
    ItemsetRole,
    PatternType,
)
from ..mixins import CreatedAtMixin, SoftDeleteMixin, pg_enum


class GeneralizedPattern(SoftDeleteMixin, table=True):
    __tablename__ = "generalized_patterns"
    __table_args__ = (
        UniqueConstraint(
            "pattern_type",
            "pattern_class",
            name="uq_generalized_patterns_type_class",
        ),
        CheckConstraint(
            "support IS NULL OR support BETWEEN 0.0 AND 1.0",
            name="support_range",
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0.0 AND 1.0",
            name="confidence_range",
        ),
        CheckConstraint("lift IS NULL OR lift >= 0.0", name="lift_non_negative"),
    )

    id: int | None = Field(default=None, primary_key=True)
    pattern_type: PatternType = Field(
        sa_column=Column(pg_enum(PatternType, "pattern_type"), nullable=False)
    )
    pattern_class: str = Field(sa_column=Column(String, nullable=False))
    description: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    support: float | None = None
    confidence: float | None = None
    lift: float | None = None


class PatternItem(SoftDeleteMixin, table=True):
    __tablename__ = "pattern_items"
    __table_args__ = (
        CheckConstraint(
            "position IS NULL OR position >= 0",
            name="position_non_negative",
        ),
        CheckConstraint(
            "("
            "item_kind = 'TOKEN_CLASS' "
            "AND token_class_id IS NOT NULL "
            "AND phrase_id IS NULL "
            "AND semantic_class_id IS NULL "
            "AND target_field_id IS NULL"
            ") OR ("
            "item_kind = 'PHRASE' "
            "AND token_class_id IS NULL "
            "AND phrase_id IS NOT NULL "
            "AND semantic_class_id IS NULL "
            "AND target_field_id IS NULL"
            ") OR ("
            "item_kind = 'SEMANTIC_CLASS' "
            "AND token_class_id IS NULL "
            "AND phrase_id IS NULL "
            "AND semantic_class_id IS NOT NULL "
            "AND target_field_id IS NULL"
            ") OR ("
            "item_kind = 'TARGET_FIELD' "
            "AND token_class_id IS NULL "
            "AND phrase_id IS NULL "
            "AND semantic_class_id IS NULL "
            "AND target_field_id IS NOT NULL"
            ")",
            name="typed_reference_matches_item_kind",
        ),
        Index(
            "ix_pattern_items_pattern_position_role",
            "pattern_id",
            "position",
            "role",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    pattern_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("generalized_patterns.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    position: int | None = None
    role: ItemsetRole = Field(
        default=ItemsetRole.NONE,
        sa_column=Column(
            pg_enum(ItemsetRole, "itemset_role"),
            nullable=False,
            server_default=text("'NONE'"),
        ),
    )
    item_kind: ItemKind = Field(
        sa_column=Column(pg_enum(ItemKind, "item_kind"), nullable=False)
    )
    token_class_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("token_classes.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    phrase_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("phrases.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    semantic_class_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("semantic_classes.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    target_field_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("target_fields.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )


class PatternInstance(CreatedAtMixin, table=True):
    __tablename__ = "pattern_instances"
    __table_args__ = (
        CheckConstraint(
            "confidence BETWEEN 0.0 AND 1.0",
            name="confidence_range",
        ),
        Index(
            "ix_pattern_instances_pattern_run",
            "pattern_id",
            "extraction_run_id",
        ),
        Index("ix_pattern_instances_extraction_run_id", "extraction_run_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    pattern_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("generalized_patterns.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    extraction_run_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    confidence: float
    discovered_by: DiscoveryMethod = Field(
        sa_column=Column(
            pg_enum(DiscoveryMethod, "discovery_method"),
            nullable=False,
        )
    )
    discovered_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class PatternInstanceMatch(CreatedAtMixin, table=True):
    __tablename__ = "pattern_instance_matches"
    __table_args__ = (
        CheckConstraint(
            "matched_position IS NULL OR matched_position >= 0",
            name="matched_position_non_negative",
        ),
        Index("ix_pattern_instance_matches_element_id", "element_id"),
    )

    pattern_instance_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("pattern_instances.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    element_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("elements.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    matched_position: int | None = None
