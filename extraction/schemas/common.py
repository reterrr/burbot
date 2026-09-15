from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, func
from sqlalchemy import Enum as SAEnum


def utc_now() -> datetime:
    return datetime.now(UTC)


def id_column() -> Column:
    return Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


def reference(target: str, *, nullable: bool = False, primary_key: bool = False) -> Column:
    return Column(
        BigInteger,
        ForeignKey(target, ondelete="RESTRICT"),
        nullable=nullable,
        primary_key=primary_key,
    )


def created_at_column() -> Column:
    return Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


def pg_enum(enum_class: type[StrEnum], name: str) -> SAEnum:
    return SAEnum(
        enum_class,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=lambda members: [str(member.value) for member in members],
    )
