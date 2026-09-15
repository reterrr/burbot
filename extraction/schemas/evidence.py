"""Reusable definitions and immutable evidence registered by the active backend."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from extraction.schemas.common import id_column, pg_enum, reference, utc_now
from extraction.schemas.enums import (
    AnchorRelationKind,
    DiscoveryMethod,
    ElementFrom,
    ExtractionIssueCode,
    SelectorType,
)
from sources.schemas.common import CreatedAtMixin


def json_column(*, nullable=True):
    return Column(JSONB().with_variant(JSON(), "sqlite"), nullable=nullable)


class TokenClass(CreatedAtMixin, table=True):
    __tablename__ = "token_classes"
    # Preserve existing string IDs (e.g. "text", "date") used by /extractions.
    id: str = Field(sa_column=Column(String(150), primary_key=True))
    name: str = Field(sa_column=Column(String(150), nullable=False, unique=True))
    validation_regex: str | None = Field(default=None, sa_column=Column(Text))
    parser_name: str | None = None
    description: str | None = Field(default=None, sa_column=Column(Text))


class Element(CreatedAtMixin, table=True):
    __tablename__ = "elements"
    __table_args__ = (
        Index("ix_elements_run_parent", "extraction_run_id", "parent_element_id"),
        Index("ix_elements_structural_hash", "structural_hash"),
        CheckConstraint("child_index IS NULL OR child_index >= 0", name="elements_child_index"),
        CheckConstraint("depth IS NULL OR depth >= 0", name="elements_depth"),
    )
    id: int | None = Field(default=None, sa_column=id_column())
    extraction_run_id: int = Field(sa_column=reference("extraction_runs.id"))
    parent_element_id: int | None = Field(
        default=None, sa_column=reference("elements.id", nullable=True)
    )
    child_index: int | None = None
    depth: int | None = None
    element_from: ElementFrom = Field(
        sa_column=Column(pg_enum(ElementFrom, "extraction_element_from"), nullable=False)
    )
    text_content: str | None = Field(default=None, sa_column=Column(Text))
    structural_hash: str | None = Field(default=None, sa_column=Column(String(64)))


class ElementHTML(CreatedAtMixin, table=True):
    __tablename__ = "elements_html"
    element_id: int = Field(sa_column=reference("elements.id", primary_key=True))
    dom_path: str | None = Field(default=None, sa_column=Column(Text))
    absolute_xpath: str | None = Field(default=None, sa_column=Column(Text))
    css_path: str | None = Field(default=None, sa_column=Column(Text))
    tag_name: str | None = None
    attributes_json: dict[str, Any] | None = Field(default=None, sa_column=json_column())


class ElementPDF(CreatedAtMixin, table=True):
    __tablename__ = "elements_pdf"
    __table_args__ = (
        CheckConstraint("page_number > 0", name="pdf_page_number"),
        CheckConstraint("x1 IS NULL OR x0 IS NULL OR x1 >= x0", name="pdf_x_bounds"),
        CheckConstraint("y1 IS NULL OR y0 IS NULL OR y1 >= y0", name="pdf_y_bounds"),
        CheckConstraint(
            "ocr_confidence IS NULL OR ocr_confidence BETWEEN 0 AND 1", name="pdf_ocr_confidence"
        ),
    )
    element_id: int = Field(sa_column=reference("elements.id", primary_key=True))
    page_number: int
    x0: float | None = None
    y0: float | None = None
    x1: float | None = None
    y1: float | None = None
    block_number: int | None = None
    line_number: int | None = None
    word_number: int | None = None
    font_name: str | None = None
    font_size: float | None = None
    ocr_confidence: float | None = None


class ElementXLSX(CreatedAtMixin, table=True):
    __tablename__ = "elements_xlsx"
    element_id: int = Field(sa_column=reference("elements.id", primary_key=True))
    sheet_name: str
    cell_range: str


class AnchorElementReference(CreatedAtMixin, table=True):
    __tablename__ = "anchor_element_references"
    anchor_element_id: int = Field(sa_column=reference("elements.id", primary_key=True))
    target_element_id: int = Field(sa_column=reference("elements.id", primary_key=True))
    relation_kind: AnchorRelationKind = Field(
        sa_column=Column(
            pg_enum(AnchorRelationKind, "extraction_anchor_relation"), primary_key=True
        )
    )
    relative_offset: int | None = None
    confidence: float | None = None
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1", name="anchor_confidence"
        ),
        Index("ix_anchor_target", "target_element_id"),
    )


class SourceScope(CreatedAtMixin, table=True):
    __tablename__ = "source_scopes"
    __table_args__ = (
        UniqueConstraint("source_id", "name", "version", name="uq_scope_version"),
        Index(
            "uq_scope_current",
            "source_id",
            "name",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
            sqlite_where=text("valid_to IS NULL"),
        ),
        CheckConstraint("version > 0", name="scope_version_positive"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="scope_validity"),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="scope_confidence"),
    )
    id: int | None = Field(default=None, sa_column=id_column())
    source_id: int = Field(sa_column=reference("sources.id"))
    parent_scope_id: int | None = Field(
        default=None, sa_column=reference("source_scopes.id", nullable=True)
    )
    business_entity_id: int | None = Field(
        default=None, sa_column=reference("business_entities.id", nullable=True)
    )
    name: str = Field(sa_column=Column(String(150), nullable=False))
    selector_type: SelectorType = Field(
        sa_column=Column(pg_enum(SelectorType, "extraction_selector_type"), nullable=False)
    )
    selector_string: str = Field(sa_column=Column(Text, nullable=False))
    confidence_score: float = 1.0
    discovered_by: DiscoveryMethod = Field(
        default=DiscoveryMethod.MANUAL,
        sa_column=Column(pg_enum(DiscoveryMethod, "extraction_discovery_method"), nullable=False),
    )
    version: int = 1
    valid_from: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    valid_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class ScopeInstance(CreatedAtMixin, table=True):
    __tablename__ = "scope_instances"
    __table_args__ = (
        UniqueConstraint(
            "extraction_run_id", "scope_id", "root_element_id", name="uq_scope_instance_root"
        ),
        CheckConstraint("occurrence_index >= 0", name="scope_occurrence_nonnegative"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="scope_instance_confidence"),
        Index("ix_scope_instances_parent", "parent_scope_instance_id"),
        Index("ix_scope_instances_hash", "instance_hash"),
    )
    id: int | None = Field(default=None, sa_column=id_column())
    scope_id: int = Field(sa_column=reference("source_scopes.id"))
    extraction_run_id: int = Field(sa_column=reference("extraction_runs.id"))
    parent_scope_instance_id: int | None = Field(
        default=None, sa_column=reference("scope_instances.id", nullable=True)
    )
    root_element_id: int = Field(sa_column=reference("elements.id"))
    occurrence_index: int = 0
    instance_hash: str | None = Field(default=None, sa_column=Column(String(64)))
    confidence: float = 1.0


class FieldSelector(CreatedAtMixin, table=True):
    """Append-only field recipe: optional locator + validated extraction operation.

    The historical table name is retained. NULL extraction_json marks pre-recipe
    rows whose behavior is unknown; execution requires manual rediscovery.
    Only pageUrl recipes may omit the locator. New rows are validated by the
    extraction repository, including copies made during scope rollover.
    """

    __tablename__ = "field_selectors"
    __table_args__ = (
        UniqueConstraint(
            "scope_id", "source_field_tracking_id", "version", name="uq_selector_version"
        ),
        Index(
            "uq_selector_current",
            "scope_id",
            "source_field_tracking_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
            sqlite_where=text("valid_to IS NULL"),
        ),
        CheckConstraint("version > 0", name="selector_version_positive"),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="selector_confidence"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="selector_validity"),
        CheckConstraint(
            "(selector_type IS NULL) = (selector_string IS NULL)",
            name="selector_complete_locator",
        ),
    )
    id: int | None = Field(default=None, sa_column=id_column())
    scope_id: int = Field(sa_column=reference("source_scopes.id"))
    source_field_tracking_id: int = Field(sa_column=reference("source_field_trackings.id"))
    selector_type: SelectorType | None = Field(
        default=None,
        sa_column=Column(pg_enum(SelectorType, "extraction_selector_type"), nullable=True),
    )
    selector_string: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    extraction_json: dict[str, Any] | None = Field(default=None, sa_column=json_column())
    confidence_score: float = 1.0
    discovered_by: DiscoveryMethod = Field(
        default=DiscoveryMethod.MANUAL,
        sa_column=Column(pg_enum(DiscoveryMethod, "extraction_discovery_method"), nullable=False),
    )
    version: int = 1
    valid_from: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    valid_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class GroundTruth(CreatedAtMixin, table=True):
    __tablename__ = "ground_truth"
    id: int | None = Field(default=None, sa_column=id_column())
    field_observation_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("field_observations.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        )
    )
    confirmed_by: str = "HUMAN"
    confirmed_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )


class ExtractionCapture(CreatedAtMixin, table=True):
    __tablename__ = "extraction_captures"
    run_id: int = Field(sa_column=reference("extraction_runs.id", primary_key=True))
    capture_key: str = Field(sa_column=Column(String(150), nullable=False, unique=True))
    payload_hash: str = Field(sa_column=Column(String(64), nullable=False))
    result_json: dict[str, Any] = Field(sa_column=json_column(nullable=False))


class ExtractionIssue(CreatedAtMixin, table=True):
    __tablename__ = "extraction_issues"
    id: int | None = Field(default=None, sa_column=id_column())
    extraction_run_id: int = Field(sa_column=reference("extraction_runs.id"))
    code: ExtractionIssueCode = Field(
        sa_column=Column(pg_enum(ExtractionIssueCode, "extraction_issue_code"), nullable=False)
    )
    scope_instance_id: int | None = Field(
        default=None, sa_column=reference("scope_instances.id", nullable=True)
    )
    business_entity_field_id: int | None = Field(
        default=None, sa_column=reference("business_entity_fields.id", nullable=True)
    )
    message: str = Field(sa_column=Column(Text, nullable=False))


EVIDENCE_TABLES = tuple(
    model.__table__
    for model in (
        TokenClass,
        Element,
        ElementHTML,
        ElementPDF,
        ElementXLSX,
        AnchorElementReference,
        SourceScope,
        ScopeInstance,
        FieldSelector,
        GroundTruth,
        ExtractionCapture,
        ExtractionIssue,
    )
)
