"""Append-only source history, independent of semantic schema revisions."""
from datetime import datetime
from sqlalchemy import BigInteger, Column, ForeignKey, ForeignKeyConstraint, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel
from .entities import created_at_column, utc_now


class BusinessDefinitionCodeVersion(SQLModel, table=True):
    __tablename__ = "business_definition_code_versions"
    __table_args__ = (
        UniqueConstraint("business_model_id", "version", name="uq_business_definition_code_version"),
        ForeignKeyConstraint(
            ["business_model_id", "schema_revision_id"],
            ["business_model_revisions.business_model_id", "business_model_revisions.id"],
            name="fk_business_definition_code_schema_own", ondelete="RESTRICT",
        ),
    )
    id: int | None = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    business_model_id: int = Field(sa_column=Column(BigInteger, ForeignKey("business_models.id", ondelete="RESTRICT"), nullable=False))
    version: int
    code: str = Field(sa_column=Column(Text, nullable=False))
    sha256: str = Field(sa_column=Column(String(64), nullable=False))
    schema_revision_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    reason: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())
