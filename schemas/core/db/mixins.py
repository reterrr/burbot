"""Reusable timestamp columns and PostgreSQL enum helpers."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql.type_api import TypeEngine
from sqlmodel import Field, SQLModel

from . import base as _base  # noqa: F401  # configure metadata before tables


def utc_now() -> datetime:
    """Return an aware UTC timestamp for application-side defaults."""

    return datetime.now(UTC)


def pg_enum[EnumT: Enum](
    enum_class: type[EnumT],
    name: str,
) -> TypeEngine[Any]:
    """Create a named native PostgreSQL enum with stable stored values."""

    def values(members: type[EnumT]) -> list[str]:
        return [str(member.value) for member in members]

    return SAEnum(
        enum_class,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=values,
    )


class CreatedAtMixin(SQLModel):
    """For append-only and current-state rows."""

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "nullable": False,
            "server_default": func.now(),
        },
    )


class UpdatedAtMixin(CreatedAtMixin):
    """For editable/current-state rows."""

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "nullable": False,
            "server_default": func.now(),
            "onupdate": func.now(),
        },
    )


class SoftDeleteMixin(UpdatedAtMixin):
    """For recoverable deletion of master/configuration rows only."""

    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={"nullable": True},
    )
