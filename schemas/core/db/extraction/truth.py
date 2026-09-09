"""Human/system-confirmed labels used for validation and future training."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
)
from sqlmodel import Field

from ..enums import ConfirmedBy
from ..mixins import SoftDeleteMixin, pg_enum


class GroundTruth(SoftDeleteMixin, table=True):
    """Store a human- or system-confirmed label for later validation.

    :ivar id: Database primary key.
    :ivar source_id: Identifier of the related sources.
    :ivar target_field_id: Identifier of the related target field.
    :ivar project_id: Identifier of the related project.
    :ivar operator_id: Identifier of the related operator.
    :ivar recruitment_id: Identifier of the related recruitment.
    :ivar element_id: Identifier of the related element.
    :ivar concrete_value_id: Identifier of the related concrete value.
    :ivar value: Value.
    :ivar confirmed_by: Confirmed by.
    :ivar confirmed_at: Timestamp for confirmed.
    :ivar notes: Optional notes supplied by an operator or importer.
    """
    __tablename__ = "ground_truth"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(project_id, operator_id, recruitment_id) = 1",
            name="exactly_one_business_entity",
        ),
        Index("ix_ground_truth_source_field", "source_id", "target_field_id"),
        Index("ix_ground_truth_project_id", "project_id"),
        Index("ix_ground_truth_operator_id", "operator_id"),
        Index("ix_ground_truth_recruitment_id", "recruitment_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    source_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("sources.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    target_field_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("target_fields.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    project_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    operator_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("operators.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    recruitment_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("recruitments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    element_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("elements.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    concrete_value_id: int | None = Field(
        default=None,
        sa_column=Column(
            Integer,
            ForeignKey("concrete_values.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    value: str = Field(sa_column=Column(Text, nullable=False))
    confirmed_by: ConfirmedBy = Field(
        sa_column=Column(pg_enum(ConfirmedBy, "confirmed_by"), nullable=False)
    )
    confirmed_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
