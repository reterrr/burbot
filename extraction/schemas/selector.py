"""Persistent selector identities, versioned recipes, and concrete locators.

Selector -> SelectorVersion -> concrete rows is one-to-many at both steps.
A version may carry several strategies, including multiple rows of the same kind.
DOMPoint is an embedded coordinate, not an independently owned selector.
"""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, NonNegativeInt, model_validator
from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from extraction.schemas.common import id_column, pg_enum, reference, utc_now
from extraction.schemas.enums import DiscoveryMethod
from sources.schemas.common import CreatedAtMixin


def json_column(*, nullable=True):
    return Column(JSONB().with_variant(JSON(), "sqlite"), nullable=nullable)


class SelectorType(StrEnum):
    CSS_PATH = "css_path"
    XPATH = "xpath"
    DOM_PATH = "dom_path"
    ELEMENT_ID = "element_id"
    DOM_RANGE = "dom_range"
    EXACT_POS = "exact_pos"
    TEXT_POSITION = "text_position"
    TEXT_QUOTE = "text_quote"
    TEXT_FRAGMENT = "text_fragment"


class Selector(CreatedAtMixin, table=True):
    """Stable selector identity; locator content belongs to its versions."""
    __tablename__ = "selectors"
    id: int | None = Field(default=None, sa_column=id_column())
    source_field_tracking_id: int = Field(sa_column=reference("source_field_trackings.id"))


class SelectorVersion(CreatedAtMixin, table=True):
    __tablename__ = "selector_versions"
    __table_args__ = (
        UniqueConstraint("selector_id", "version", name="uq_selector_versions_number"),
        CheckConstraint("version > 0", name="selector_versions_positive"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="selector_versions_validity"),
        Index("uq_selector_versions_current", "selector_id", unique=True,
              postgresql_where=text("valid_to IS NULL"), sqlite_where=text("valid_to IS NULL")),
    )
    id: int | None = Field(default=None, sa_column=id_column())
    selector_id: int = Field(sa_column=reference("selectors.id"))
    version: int = Field(default=1, gt=0)
    extraction_json: dict | None = Field(default=None, sa_column=json_column())
    discovered_by: DiscoveryMethod = Field(
        default=DiscoveryMethod.MANUAL,
        sa_column=Column(pg_enum(DiscoveryMethod, "extraction_discovery_method"), nullable=False))
    valid_from: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    valid_to: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class SelectorBase(CreatedAtMixin):
    """Each concrete table has its own primary key and a real version FK.

    No uniqueness on selector_version_id: repeated implementations are allowed.
    Use model_validate at input boundaries; SQLModel table construction is not
    request validation. Database checks protect persisted scalar invariants.
    """
    id: int | None = Field(default=None, primary_key=True, sa_type=BigInteger().with_variant(Integer, "sqlite"))
    selector_version_id: int = Field(sa_type=BigInteger, foreign_key="selector_versions.id", index=True, ondelete="RESTRICT")


class CSSPathSelector(SelectorBase, table=True):
    __tablename__ = "selector_css_paths"
    __table_args__ = (CheckConstraint("length(trim(value)) > 0", name="selector_css_value"),)
    value: str = Field(min_length=1, sa_type=Text)


class XPathSelector(SelectorBase, table=True):
    __tablename__ = "selector_xpaths"
    __table_args__ = (CheckConstraint("length(trim(value)) > 0", name="selector_xpath_value"),)
    value: str = Field(min_length=1, sa_type=Text)


class DOMPathSelector(SelectorBase, table=True):
    __tablename__ = "selector_dom_paths"
    __table_args__ = (CheckConstraint("root IN ('document', 'body')", name="selector_dom_path_root"),)
    path: list[NonNegativeInt] = Field(sa_column=json_column(nullable=False))
    root: Literal["document", "body"] = Field(default="document", sa_type=String)


class ElementIdSelector(SelectorBase, table=True):
    __tablename__ = "selector_element_ids"
    __table_args__ = (CheckConstraint("length(trim(value)) > 0", name="selector_element_id_value"),)
    value: str = Field(min_length=1, sa_type=Text)


class DOMPoint(SQLModel):
    model_config = ConfigDict(extra="forbid")
    path: list[NonNegativeInt]
    offset: NonNegativeInt


class DOMRangeSelector(SelectorBase, table=True):
    __tablename__ = "selector_dom_ranges"
    __table_args__ = (
        CheckConstraint("root IN ('document', 'body')", name="selector_dom_range_root"),
        CheckConstraint("start_offset >= 0 AND end_offset >= 0", name="selector_dom_range_offsets"),
    )
    root: Literal["document", "body"] = Field(default="document", sa_type=String)
    start_path: list[NonNegativeInt] = Field(sa_column=json_column(nullable=False))
    start_offset: int = Field(ge=0)
    end_path: list[NonNegativeInt] = Field(sa_column=json_column(nullable=False))
    end_offset: int = Field(ge=0)


class ExactPosSelector(SelectorBase, table=True):
    __tablename__ = "selector_exact_positions"
    __table_args__ = (CheckConstraint("char_start >= 0 AND char_end > char_start", name="selector_exact_range"),)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)


    @model_validator(mode="after")
    def validate_range(self):
        if self.char_end <= self.char_start:
            raise ValueError("char_end must be greater than char_start")
        return self


class TextPositionSelector(SelectorBase, table=True):
    __tablename__ = "selector_text_positions"
    __table_args__ = (CheckConstraint('start >= 0 AND "end" > start', name="selector_text_position_range"),)
    start: int = Field(ge=0)
    end: int = Field(gt=0)


    @model_validator(mode="after")
    def validate_range(self):
        if self.end <= self.start:
            raise ValueError("end must be greater than start")
        return self


class TextQuoteSelector(SelectorBase, table=True):
    __tablename__ = "selector_text_quotes"
    __table_args__ = (CheckConstraint("length(exact) > 0", name="selector_text_quote_exact"),)
    exact: str = Field(min_length=1, sa_type=Text)
    prefix: str | None = Field(default=None, sa_type=Text)
    suffix: str | None = Field(default=None, sa_type=Text)


class TextFragmentSelector(SelectorBase, table=True):
    __tablename__ = "selector_text_fragments"
    __table_args__ = (CheckConstraint("length(trim(value)) > 0", name="selector_text_fragment_value"),)
    value: str = Field(min_length=1, sa_type=Text)


CONCRETE_SELECTOR_MODELS = (
    CSSPathSelector, XPathSelector, DOMPathSelector, ElementIdSelector,
    DOMRangeSelector, ExactPosSelector, TextPositionSelector,
    TextQuoteSelector, TextFragmentSelector,
)
EVIDENCE_TABLES = tuple(model.__table__ for model in (Selector, SelectorVersion, *CONCRETE_SELECTOR_MODELS))
