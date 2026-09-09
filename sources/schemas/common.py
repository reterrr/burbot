"""Reusable timestamp columns and PostgreSQL enum helpers."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql.type_api import TypeEngine
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp.

    :return: Current timezone-aware UTC timestamp.
    """

    return datetime.now(UTC)


def pg_enum[EnumT: Enum](
    enum_class: type[EnumT],
    name: str,
) -> TypeEngine[Any]:
    """Build a named native PostgreSQL enum that stores member values.

    :param enum_class: Enum class represented by the database type.
    :param name: Human-readable or database type name, depending on context.
    :return: Configured SQLAlchemy PostgreSQL enum type.
    """

    def values(members: type[EnumT]) -> list[str]:
        """Convert enum members to their stable database values.

        :param members: Enum class whose member values should be returned.
        :return: String values persisted for the enum members.
        """
        return [str(member.value) for member in members]

    return SAEnum(
        enum_class,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=values,
    )


class CreatedAtMixin(SQLModel):
    """Provide reusable created at fields.

    :ivar created_at: Timestamp at which the record was created.
    """

    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "nullable": False,
            "server_default": func.now(),
        },
    )


class UpdatedAtMixin(CreatedAtMixin):
    """Provide reusable updated at fields.

    :ivar updated_at: Timestamp at which the record was last updated.
    """

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "nullable": False,
            "server_default": func.now(),
            "onupdate": func.now(),
        },
    )
