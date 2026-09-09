from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Annotated

from pydantic import BaseModel, StringConstraints, Field


@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int
    end_line: int
    end_column: int


# TODO: encrypt table_name
# TODO: whole encryption journey
class Sema:
    class Type(StrEnum):
        STRING = "String"
        TEXT = "Text"
        INTEGER = "Integer"
        BIG_INTEGER = "BigInteger"
        FLOAT = "Float"
        DECIMAL = "Decimal"
        BOOLEAN = "Boolean"
        DATE = "Date"
        DATETIME = "DateTime"
        UUID = "UUID"
        JSON = "JSON"
        REFERENCE = "Reference"

    class SemaException(Exception):
        def __init__(
                self,
                description: str,
                location: SourceLocation,
        ) -> None:
            self.description = description
            self.location = location

            super().__init__(
                f"{description} "
                f"at {location.line}:{location.column}"
            )

    TableName = Annotated[
        str,
        StringConstraints(
            min_length=1,
            max_length=54,
        ),
    ]

    class Field(BaseModel):
        name: str
        type: "Sema.Type"
        location: SourceLocation

        nullable: bool = True
        unique: bool = False
        index: bool = False
        primary_key: bool = False

        default: Any | None = None

        # String
        min_length: int | None = None
        max_length: int | None = None
        pattern: str | None = None

        # Numeric
        gt: int | float | None = None
        ge: int | float | None = None
        lt: int | float | None = None
        le: int | float | None = None

        # Decimal
        precision: int | None = None
        scale: int | None = None

        # Reference
        reference: str | None = None

    class Entity(BaseModel):
        name: str
        location: SourceLocation

        tablename: "Sema.TableName"

        fields: list["Sema.Field"] = Field(
            default_factory=list
        )

    class Schema(BaseModel):
        entities: list["Sema.Entity"] = Field(
            default_factory=list
        )

    RESERVED_ENTITY_NAMES = {
        "Entity",
        "Field",
        "String",
        "Text",
        "Integer",
        "BigInteger",
        "Float",
        "Decimal",
        "Boolean",
        "Date",
        "DateTime",
        "UUID",
        "JSON",
        "Reference",
    }

    RESERVED_FIELD_NAMES = {
        "id"
    }

    TABLE_NAME_PATTERN = re.compile(r"^e_[a-z2-7]{52}$")

    def validate(
            self,
            schema: Sema.Schema,
    ) -> Sema.Schema:
        """
        Revalidate an already semantically analyzed schema
        received from an untrusted client.

        Does not parse or transform the schema.
        """

        self._validate_entities(schema)
        self._validate_references(schema)

        return schema

    def _validate_entities(
            self,
            schema: Sema.Schema,
    ) -> None:
        entity_names: set[str] = set()
        table_names: set[str] = set()

        for entity in schema.entities:
            self._validate_entity_name(
                entity,
                entity_names,
            )
            entity_names.add(entity.name)

            self._validate_table_name(
                entity,
                table_names,
            )
            table_names.add(entity.tablename)

            self._validate_entity(entity)

    def _validate_entity_name(
            self,
            entity: Sema.Entity,
            existing_names: set[str],
    ) -> None:
        if entity.name in self.RESERVED_ENTITY_NAMES:
            raise self.SemaException(
                description=(
                    f"Entity name '{entity.name}' is reserved"
                ),
                location=entity.location,
            )

        if entity.name in existing_names:
            raise self.SemaException(
                description=(
                    f"Entity '{entity.name}' is already defined"
                ),
                location=entity.location,
            )

        if not entity.name.isidentifier():
            raise self.SemaException(
                description=(
                    f"Invalid entity name '{entity.name}'"
                ),
                location=entity.location,
            )

    def _validate_entity(
            self,
            entity: Sema.Entity,
    ) -> None:
        field_names: set[str] = set()
        primary_keys: list[Sema.Field] = []

        for field_value in entity.fields:
            if field_value.name in self.RESERVED_FIELD_NAMES:
                raise self.SemaException(
                    description=(
                        f"Field name '{field_value.name}' is reserved"
                    ),
                    location=field_value.location,
                )

            if field_value.name in field_names:
                raise self.SemaException(
                    description=(
                        f"Field '{field_value.name}' "
                        f"is already defined in entity "
                        f"'{entity.name}'"
                    ),
                    location=field_value.location,
                )

            if not field_value.name.isidentifier():
                raise self.SemaException(
                    description=(
                        f"Invalid field name "
                        f"'{field_value.name}'"
                    ),
                    location=field_value.location,
                )

            field_names.add(field_value.name)

            self._validate_field(field_value)

            if field_value.primary_key:
                primary_keys.append(field_value)

        if len(primary_keys) > 1:
            raise self.SemaException(
                description=(
                    f"Entity '{entity.name}' has "
                    f"multiple primary key fields"
                ),
                location=entity.location,
            )

    def _validate_field(
            self,
            field_value: Sema.Field,
    ) -> None:
        self._validate_boolean_options(field_value)
        self._validate_constraint_compatibility(field_value)

        if field_value.primary_key and field_value.nullable:
            raise self.SemaException(
                description=(
                    f"Primary key field '{field_value.name}' "
                    f"cannot be nullable"
                ),
                location=field_value.location,
            )

        if field_value.type == self.Type.STRING:
            self._validate_string_field(field_value)

        if field_value.type in {
            self.Type.INTEGER,
            self.Type.BIG_INTEGER,
            self.Type.FLOAT,
            self.Type.DECIMAL,
        }:
            self._validate_numeric_field(field_value)

        if field_value.type == self.Type.DECIMAL:
            self._validate_decimal_field(field_value)

        if field_value.type == self.Type.REFERENCE:
            if field_value.reference is None:
                raise self.SemaException(
                    description=(
                        f"Reference field '{field_value.name}' "
                        f"must specify a target entity"
                    ),
                    location=field_value.location,
                )

        elif field_value.reference is not None:
            raise self.SemaException(
                description=(
                    f"Field '{field_value.name}' is not a "
                    f"Reference but has a reference target"
                ),
                location=field_value.location,
            )

    def _validate_constraint_compatibility(
            self,
            field_value: Sema.Field,
    ) -> None:
        if field_value.type != self.Type.STRING:
            if (
                    field_value.min_length is not None
                    or field_value.max_length is not None
                    or field_value.pattern is not None
            ):
                raise self.SemaException(
                    description=(
                        f"String constraints cannot be used "
                        f"with type '{field_value.type.value}'"
                    ),
                    location=field_value.location,
                )

        numeric_types = {
            self.Type.INTEGER,
            self.Type.BIG_INTEGER,
            self.Type.FLOAT,
            self.Type.DECIMAL,
        }

        if field_value.type not in numeric_types:
            if any(
                    value is not None
                    for value in (
                            field_value.gt,
                            field_value.ge,
                            field_value.lt,
                            field_value.le,
                    )
            ):
                raise self.SemaException(
                    description=(
                        f"Numeric constraints cannot be used "
                        f"with type '{field_value.type.value}'"
                    ),
                    location=field_value.location,
                )

        if field_value.type != self.Type.DECIMAL:
            if (
                    field_value.precision is not None
                    or field_value.scale is not None
            ):
                raise self.SemaException(
                    description=(
                        "precision/scale can only be used "
                        "with Decimal"
                    ),
                    location=field_value.location,
                )

    def _validate_references(
            self,
            schema: Sema.Schema,
    ) -> None:
        entity_names = {
            entity.name
            for entity in schema.entities
        }

        for entity in schema.entities:
            for field_value in entity.fields:
                if field_value.type != self.Type.REFERENCE:
                    continue

                assert field_value.reference is not None

                if field_value.reference not in entity_names:
                    raise self.SemaException(
                        description=(
                            f"Unknown referenced entity "
                            f"'{field_value.reference}'"
                        ),
                        location=field_value.location,
                    )

    def _validate_boolean_options(
            self,
            field_value: Sema.Field,
    ) -> None:
        options = {
            "nullable": field_value.nullable,
            "unique": field_value.unique,
            "index": field_value.index,
            "primary_key": field_value.primary_key,
        }

        for name, value in options.items():
            if not isinstance(value, bool):
                raise self.SemaException(
                    description=(
                        f"'{name}' must be a boolean"
                    ),
                    location=field_value.location,
                )

    def _validate_table_name(
            self,
            entity: Sema.Entity,
            existing_names: set[str],
    ) -> None:
        tablename = entity.tablename

        if not isinstance(tablename, str):
            raise self.SemaException(
                description=(
                    f"Entity '{entity.name}' must specify "
                    f"a valid table name"
                ),
                location=entity.location,
            )

        if not self.TABLE_NAME_PATTERN.fullmatch(tablename):
            raise self.SemaException(
                description=(
                    f"Invalid table name '{tablename}'. "
                    f"Expected a Burbot-generated table identifier"
                ),
                location=entity.location,
            )

        if tablename in existing_names:
            raise self.SemaException(
                description=(
                    f"Table name '{tablename}' "
                    f"is already used by another entity"
                ),
                location=entity.location,
            )

    def _validate_string_field(
            self,
            field_value: Sema.Field,
    ) -> None:
        if field_value.min_length is not None:
            if (
                    not isinstance(field_value.min_length, int)
                    or isinstance(field_value.min_length, bool)
                    or field_value.min_length < 0
            ):
                raise self.SemaException(
                    description=(
                        "'min_length' must be a "
                        "non-negative integer"
                    ),
                    location=field_value.location,
                )

        if field_value.max_length is not None:
            if (
                    not isinstance(field_value.max_length, int)
                    or isinstance(field_value.max_length, bool)
                    or field_value.max_length <= 0
            ):
                raise self.SemaException(
                    description=(
                        "'max_length' must be "
                        "a positive integer"
                    ),
                    location=field_value.location,
                )

        if (
                field_value.min_length is not None
                and field_value.max_length is not None
                and field_value.min_length
                > field_value.max_length
        ):
            raise self.SemaException(
                description=(
                    "'min_length' cannot be greater "
                    "than 'max_length'"
                ),
                location=field_value.location,
            )

        if (
                field_value.pattern is not None
                and not isinstance(field_value.pattern, str)
        ):
            raise self.SemaException(
                description="'pattern' must be a string",
                location=field_value.location,
            )

    def _validate_numeric_field(
            self,
            field_value: Sema.Field,
    ) -> None:
        if (
                field_value.gt is not None
                and field_value.ge is not None
        ):
            raise self.SemaException(
                description=(
                    "'gt' and 'ge' cannot be used together"
                ),
                location=field_value.location,
            )

        if (
                field_value.lt is not None
                and field_value.le is not None
        ):
            raise self.SemaException(
                description=(
                    "'lt' and 'le' cannot be used together"
                ),
                location=field_value.location,
            )

        values = (
            field_value.gt,
            field_value.ge,
            field_value.lt,
            field_value.le,
        )

        for value in values:
            if value is None:
                continue

            if (
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
            ):
                raise self.SemaException(
                    description=(
                        "Numeric bounds must be numbers"
                    ),
                    location=field_value.location,
                )

        lower = (
            field_value.gt
            if field_value.gt is not None
            else field_value.ge
        )

        upper = (
            field_value.lt
            if field_value.lt is not None
            else field_value.le
        )

        if (
                lower is not None
                and upper is not None
                and lower > upper
        ):
            raise self.SemaException(
                description=(
                    "Lower numeric bound cannot be "
                    "greater than upper bound"
                ),
                location=field_value.location,
            )

    def _validate_decimal_field(
            self,
            field_value: Sema.Field,
    ) -> None:
        if field_value.precision is not None:
            if (
                    not isinstance(field_value.precision, int)
                    or isinstance(field_value.precision, bool)
                    or field_value.precision <= 0
            ):
                raise self.SemaException(
                    description=(
                        "'precision' must be "
                        "a positive integer"
                    ),
                    location=field_value.location,
                )

        if field_value.scale is not None:
            if (
                    not isinstance(field_value.scale, int)
                    or isinstance(field_value.scale, bool)
                    or field_value.scale < 0
            ):
                raise self.SemaException(
                    description=(
                        "'scale' must be "
                        "a non-negative integer"
                    ),
                    location=field_value.location,
                )

        if (
                field_value.precision is not None
                and field_value.scale is not None
                and field_value.scale
                > field_value.precision
        ):
            raise self.SemaException(
                description=(
                    "'scale' cannot be greater "
                    "than 'precision'"
                ),
                location=field_value.location,
            )
