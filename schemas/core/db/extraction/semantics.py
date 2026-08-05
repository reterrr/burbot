"""Phrases, semantic classes and their learned/manual classifications."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field

from ..enums import DiscoveryMethod
from ..mixins import SoftDeleteMixin, pg_enum


class Phrase(SoftDeleteMixin, table=True):
    __tablename__ = "phrases"

    id: int | None = Field(default=None, primary_key=True)
    phrase: str = Field(sa_column=Column(Text, nullable=False, unique=True))
    normalized_phrase: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )


class SemanticClass(SoftDeleteMixin, table=True):
    __tablename__ = "semantic_classes"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String, nullable=False, unique=True))
    description: str | None = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
    )


class PhraseClassification(SoftDeleteMixin, table=True):
    __tablename__ = "phrase_classifications"
    __table_args__ = (
        UniqueConstraint(
            "phrase_id",
            "semantic_class_id",
            "discovered_by",
            name="uq_phrase_classifications_phrase_class_method",
        ),
        CheckConstraint(
            "confidence BETWEEN 0.0 AND 1.0",
            name="confidence_range",
        ),
        Index(
            "ix_phrase_classifications_semantic_class_id",
            "semantic_class_id",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    phrase_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("phrases.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    semantic_class_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("semantic_classes.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    confidence: float
    discovered_by: DiscoveryMethod = Field(
        sa_column=Column(
            pg_enum(DiscoveryMethod, "discovery_method"),
            nullable=False,
        )
    )
