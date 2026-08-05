"""Concrete HTML/PDF elements and technical literal values."""

from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from ..enums import AnchorRelationKind, DiscoveryMethod, ElementFrom
from ..mixins import CreatedAtMixin, pg_enum


class Element(CreatedAtMixin, table=True):
    __tablename__ = "elements"
    __table_args__ = (
        CheckConstraint(
            "child_index IS NULL OR child_index >= 0",
            name="child_index_non_negative",
        ),
        CheckConstraint("depth IS NULL OR depth >= 0", name="depth_non_negative"),
        Index(
            "ix_elements_run_parent",
            "extraction_run_id",
            "parent_element_id",
        ),
        Index("ix_elements_structural_hash", "structural_hash"),
    )

    id: int | None = Field(default=None, primary_key=True)
    extraction_run_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("extraction_runs.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    parent_element_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("elements.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    child_index: int | None = None
    depth: int | None = None
    element_from: ElementFrom = Field(
        sa_column=Column(pg_enum(ElementFrom, "element_from"), nullable=False)
    )
    text_content: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    structural_hash: str | None = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )


class ElementHTML(CreatedAtMixin, table=True):
    __tablename__ = "elements_html"

    element_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("elements.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        )
    )
    dom_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    absolute_xpath: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    css_path: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    tag_name: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    attributes_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )


class ElementPDF(CreatedAtMixin, table=True):
    __tablename__ = "elements_pdf"
    __table_args__ = (
        CheckConstraint("page_number > 0", name="page_number_positive"),
        CheckConstraint(
            "ocr_confidence IS NULL OR ocr_confidence BETWEEN 0.0 AND 1.0",
            name="ocr_confidence_range",
        ),
        CheckConstraint("x0 IS NULL OR x1 IS NULL OR x1 >= x0", name="x_bounds_order"),
        CheckConstraint("y0 IS NULL OR y1 IS NULL OR y1 >= y0", name="y_bounds_order"),
    )

    element_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("elements.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        )
    )
    page_number: int
    x0: float | None = None
    y0: float | None = None
    x1: float | None = None
    y1: float | None = None
    block_number: int | None = None
    line_number: int | None = None
    word_number: int | None = None
    font_name: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    font_size: float | None = None
    ocr_confidence: float | None = None


class AnchorElementReference(CreatedAtMixin, table=True):
    __tablename__ = "anchor_element_references"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0.0 AND 1.0",
            name="confidence_range",
        ),
        Index("ix_anchor_element_references_target", "target_element_id"),
    )

    anchor_element_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("elements.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    target_element_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("elements.id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        )
    )
    relation_kind: AnchorRelationKind = Field(
        sa_column=Column(
            pg_enum(AnchorRelationKind, "anchor_relation_kind"),
            primary_key=True,
            nullable=False,
        )
    )
    relative_offset: int | None = None
    confidence: float | None = None


class ConcreteValue(CreatedAtMixin, table=True):
    __tablename__ = "concrete_values"
    __table_args__ = (
        CheckConstraint(
            "char_start IS NULL OR char_start >= 0",
            name="char_start_non_negative",
        ),
        CheckConstraint(
            "char_end IS NULL OR char_end >= 0",
            name="char_end_non_negative",
        ),
        CheckConstraint(
            "char_start IS NULL OR char_end IS NULL OR char_end >= char_start",
            name="character_range_order",
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0.0 AND 1.0",
            name="confidence_range",
        ),
        Index("ix_concrete_values_element_id", "element_id"),
        Index("ix_concrete_values_token_class_id", "token_class_id"),
        Index("ix_concrete_values_value_hash", "value_hash"),
    )

    id: int | None = Field(default=None, primary_key=True)
    element_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("elements.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    token_class_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("token_classes.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    raw_value: str = Field(sa_column=Column(Text, nullable=False))
    normalized_value: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    char_start: int | None = None
    char_end: int | None = None
    value_hash: str | None = Field(
        default=None,
        sa_column=Column(String(64), nullable=True),
    )
    confidence: float | None = None
    discovered_by: DiscoveryMethod = Field(
        sa_column=Column(
            pg_enum(DiscoveryMethod, "discovery_method"),
            nullable=False,
        )
    )
