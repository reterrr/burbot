"""Normalized SelectorTree and independent snapshot evaluation records."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlmodel import Field, SQLModel

from extraction.schemas.common import created_at_column, id_column, reference, utc_now
from extraction.schemas.evidence import json_column


def uuid_column():
    return Column(Uuid(), unique=True, nullable=False)


class Selector(SQLModel, table=True):
    __tablename__ = "selectors"
    __table_args__ = (
        ForeignKeyConstraint(
            ["id", "active_version_id"],
            ["selector_versions.selector_id", "selector_versions.id"],
            name="fk_selectors_active_version_owner",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["business_object_field_id", "business_entity_field_id"],
            ["business_object_fields.id", "business_object_fields.business_entity_field_id"],
            name="fk_selectors_object_field_owner",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "source_id",
            "legacy_scope_name",
            "business_entity_field_id",
            name="uq_selectors_legacy_identity",
        ),
        CheckConstraint("revision >= 0", name="selector_revision_nonnegative"),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    uuid: UUID = Field(sa_column=uuid_column())
    source_id: int | None = Field(default=None, sa_column=reference("sources.id", nullable=True))
    business_entity_field_id: int = Field(sa_column=reference("business_entity_fields.id"))
    business_object_field_id: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    active_version_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    legacy_scope_name: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    revision: int = Field(
        default=0, sa_column=Column(BigInteger, nullable=False, server_default="0")
    )
    # Portable target, external source identity, page URL, and authored metadata.
    metadata_json: dict[str, Any] = Field(sa_column=json_column(nullable=False))


class SelectorVersion(SQLModel, table=True):
    __tablename__ = "selector_versions"
    __table_args__ = (
        UniqueConstraint("selector_id", "version_no", name="uq_selector_versions_number"),
        UniqueConstraint("selector_id", "id", name="uq_selector_versions_owner"),
        CheckConstraint(
            "version_no BETWEEN 1 AND 9007199254740991", name="selector_versions_safe_number"
        ),
        CheckConstraint(
            "status IN ('draft','active','superseded','rejected')",
            name="selector_versions_status",
        ),
        Index(
            "uq_selector_versions_active",
            "selector_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    uuid: UUID = Field(sa_column=uuid_column())
    selector_id: int = Field(sa_column=reference("selectors.id"))
    version_no: int = Field(sa_column=Column(BigInteger, nullable=False))
    status: str = Field(sa_column=Column(Text, nullable=False))
    created_from_snapshot_id: int | None = Field(
        default=None, sa_column=reference("source_snapshots.id", nullable=True)
    )
    # Preserve the optional origin UUID and artifact type independently of the resolved FK.
    metadata_json: dict[str, Any] = Field(sa_column=json_column(nullable=False))


class SelectorRecipe(SQLModel, table=True):
    __tablename__ = "selector_recipes"
    __table_args__ = (
        UniqueConstraint("selector_version_id", "position", name="uq_selector_recipes_order"),
        CheckConstraint(
            "position BETWEEN 0 AND 9007199254740991", name="selector_recipes_safe_order"
        ),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    uuid: UUID = Field(sa_column=uuid_column())
    selector_version_id: int = Field(sa_column=reference("selector_versions.id"))
    position: int = Field(sa_column=Column(BigInteger, nullable=False))


class SelectorPart(SQLModel, table=True):
    __tablename__ = "selector_parts"
    __table_args__ = (
        UniqueConstraint("recipe_id", "position", name="uq_selector_parts_order"),
        CheckConstraint(
            "position BETWEEN 0 AND 9007199254740991", name="selector_parts_safe_order"
        ),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    uuid: UUID = Field(sa_column=uuid_column())
    recipe_id: int = Field(sa_column=reference("selector_recipes.id"))
    position: int = Field(sa_column=Column(BigInteger, nullable=False))
    extraction_json: dict[str, Any] = Field(sa_column=json_column(nullable=False))
    join_with: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class SelectorLocator(SQLModel, table=True):
    __tablename__ = "selector_locators"
    __table_args__ = (
        UniqueConstraint("part_id", "position", name="uq_selector_locators_order"),
        CheckConstraint(
            "position BETWEEN 0 AND 9007199254740991", name="selector_locators_safe_order"
        ),
        CheckConstraint(
            "kind IN ('css_path','xpath','element_id','text_quote','dom_path','dom_range',"
            "'exact_pos','text_position','text_fragment')",
            name="selector_locators_kind",
        ),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    uuid: UUID = Field(sa_column=uuid_column())
    part_id: int = Field(sa_column=reference("selector_parts.id"))
    position: int = Field(sa_column=Column(BigInteger, nullable=False))
    kind: str = Field(sa_column=Column(Text, nullable=False))
    payload_json: dict[str, Any] = Field(sa_column=json_column(nullable=False))


class SelectorEvaluation(SQLModel, table=True):
    __tablename__ = "selector_evaluations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["extraction_run_id", "source_snapshot_id"],
            ["extraction_runs.id", "extraction_runs.source_snapshot_id"],
            name="fk_selector_evaluations_run_snapshot",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "id", "selector_version_id", "extraction_run_id", name="uq_selector_evaluation_evidence"
        ),
        UniqueConstraint(
            "extraction_run_id", "execution_key", name="uq_selector_evaluation_execution"
        ),
        CheckConstraint(
            "(provenance IN ('backend_verified', 'browser_agent_reported') "
            "AND extraction_run_id IS NOT NULL "
            "AND source_snapshot_id IS NOT NULL AND execution_key IS NOT NULL) OR "
            "(provenance = 'client_reported' AND extraction_run_id IS NULL "
            "AND execution_key IS NULL)",
            name="selector_evaluations_provenance",
        ),
        Index("ix_selector_evaluations_version", "selector_version_id", "id"),
    )

    id: int | None = Field(default=None, sa_column=id_column())
    uuid: UUID = Field(sa_column=uuid_column())
    selector_version_id: int = Field(sa_column=reference("selector_versions.id"))
    source_snapshot_id: int | None = Field(
        default=None, sa_column=reference("source_snapshots.id", nullable=True)
    )
    extraction_run_id: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    execution_key: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    evaluated_at: datetime = Field(default_factory=utc_now, sa_column=created_at_column())
    page_url: str = Field(sa_column=Column(Text, nullable=False))
    provenance: str = Field(sa_column=Column(Text, nullable=False))
    result_json: dict[str, Any] = Field(sa_column=json_column(nullable=False))


SELECTOR_TABLES = tuple(
    model.__table__
    for model in (
        Selector,
        SelectorVersion,
        SelectorRecipe,
        SelectorPart,
        SelectorLocator,
        SelectorEvaluation,
    )
)
