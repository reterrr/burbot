"""Schema language contracts and semantic analysis, independent of persistence.

``compile_source`` parses the restricted declaration language. ``Sema.validate``
revalidates JSON submitted by clients before it reaches the database.
"""

from __future__ import annotations

import keyword
import math
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    StringConstraints,
    model_validator,
)


@dataclass(frozen=True)
class SourceLocation:
    line: int
    column: int
    end_line: int
    end_column: int


class LanguageModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Sema:
    class Type(StrEnum):
        STRING = "string"
        TEXT = "text"
        INTEGER = "integer"
        BIG_INTEGER = "biginteger"
        FLOAT = "float"
        DECIMAL = "decimal"
        BOOLEAN = "boolean"
        DATE = "date"
        DATETIME = "datetime"
        UUID = "uuid"
        JSON = "json"
        REFERENCE = "reference"
        ENUM = "enum"
        SOURCE = "source"

    class SemaException(ValueError):
        def __init__(
                self, description: str, location: SourceLocation, *, code: str = "SEMANTIC_ERROR"
        ):
            self.description, self.location, self.code = description, location, code
            super().__init__(f"{description} at {location.line}:{location.column}")

        def diagnostic(self):
            from dataclasses import asdict

            return {
                "code": self.code,
                "message": self.description,
                "location": asdict(self.location),
            }

    TableName = Annotated[str, StringConstraints(min_length=1, max_length=54)]

    class EnumMember(LanguageModel):
        name: str
        value: StrictStr | StrictInt
        location: SourceLocation

    class EnumDefinition(LanguageModel):
        name: str
        members: list[Sema.EnumMember]
        location: SourceLocation

    class Field(LanguageModel):
        name: str
        persistent_key: Annotated[str, StringConstraints(min_length=1, max_length=150)]
        type: Sema.Type
        location: SourceLocation
        nullable: bool = Field(default=True, strict=True)
        unique: bool = Field(default=False, strict=True)
        index: bool = Field(default=False, strict=True)
        primary_key: bool = Field(default=False, strict=True)
        default: Any | None = None
        has_default: bool = Field(default=False, strict=True)
        min_length: int | None = Field(default=None, strict=True)
        max_length: int | None = Field(default=None, strict=True)
        pattern: str | None = None
        gt: StrictInt | StrictFloat | None = None
        ge: StrictInt | StrictFloat | None = None
        lt: StrictInt | StrictFloat | None = None
        le: StrictInt | StrictFloat | None = None
        precision: int | None = Field(default=None, strict=True)
        scale: int | None = Field(default=None, strict=True)
        reference: str | None = None
        enum_type: str | None = None
        enum_values: list[str | int] | None = None

        @model_validator(mode="before")
        @classmethod
        def default_persistent_key(cls, value):
            if isinstance(value, dict) and "persistent_key" not in value:
                return {**value, "persistent_key": value.get("name")}
            return value

    class Entity(LanguageModel):
        name: str
        location: SourceLocation
        tablename: Sema.TableName
        fields: list[Sema.Field] = Field(default_factory=list)

    class Schema(LanguageModel):
        entities: list[Sema.Entity] = Field(default_factory=list)
        enums: list[Sema.EnumDefinition] = Field(default_factory=list)

    RESERVED_ENTITY_NAMES = {
        "Entity",
        "Enum",
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
        "Source",
    }
    RESERVED_FIELD_NAMES = {"id"}
    TABLE_NAME_PATTERN = re.compile(r"^e_[a-z2-7]{52}$")

    def error(self, message, item):
        raise self.SemaException(message, item.location)

    def identifier(self, name, item):
        if (
                not name.isidentifier()
                or keyword.iskeyword(name)
                or name.startswith("_")
                or len(name) > 150
        ):
            self.error(f"Invalid identifier '{name}'", item)

    def validate(self, schema: Sema.Schema) -> Sema.Schema:
        symbols = {}
        tables = set()
        for item in [*schema.enums, *schema.entities]:
            self.identifier(item.name, item)
            if item.name in self.RESERVED_ENTITY_NAMES:
                self.error(f"Name '{item.name}' is reserved", item)
            if item.name in symbols:
                self.error(f"Name '{item.name}' is already defined", item)
            symbols[item.name] = item
        for enum in schema.enums:
            if not enum.members:
                self.error(f"Enum '{enum.name}' must have members", enum)
            names, values, types = set(), set(), set()
            for member in enum.members:
                self.identifier(member.name, member)
                if member.name in names:
                    self.error(f"Duplicate enum member '{member.name}'", member)
                if type(member.value) not in (str, int):
                    self.error("Enum values must be strings or integers", member)
                if type(member.value) is int and abs(member.value) > 2 ** 53 - 1:
                    self.error("Enum integer exceeds the portable safe-integer range", member)
                if member.value in values:
                    self.error("Enum values must be unique", member)
                names.add(member.name)
                values.add(member.value)
                types.add(type(member.value))
            if len(types) > 1:
                self.error("Enum members must all use the same value type", enum)
        entities = {item.name for item in schema.entities}
        enums = {item.name: item for item in schema.enums}
        for entity in schema.entities:
            if not self.TABLE_NAME_PATTERN.fullmatch(entity.tablename):
                self.error("Expected a Burbot-generated table identifier", entity)
            if entity.tablename in tables:
                self.error("Table name is already used by another entity", entity)
            tables.add(entity.tablename)
            names = set()
            persistent_keys = set()
            primary = 0
            for field in entity.fields:
                self.identifier(field.name, field)
                if field.name in self.RESERVED_FIELD_NAMES:
                    self.error(f"Field name '{field.name}' is reserved", field)
                if field.name in names:
                    self.error(f"Duplicate field '{field.name}'", field)
                names.add(field.name)
                if (not field.persistent_key or field.persistent_key != field.persistent_key.strip()
                        or field.persistent_key == "id"):
                    self.error(
                        "Persistent key must be nonblank, trimmed, and not reserved 'id'", field,
                    )
                if field.persistent_key in persistent_keys:
                    self.error(f"Duplicate persistent key '{field.persistent_key}'", field)
                persistent_keys.add(field.persistent_key)
                primary += bool(field.primary_key)
                self._field(field, entities, enums)
            if primary > 1:
                self.error("An entity cannot have multiple primary keys", entity)
        return schema

    def _field(self, field, entities, enums):
        kind = field.type
        if field.primary_key and field.nullable:
            self.error("Primary key cannot be nullable", field)
        if kind == self.Type.REFERENCE:
            if field.reference not in entities:
                self.error(f"Unknown referenced entity '{field.reference}'", field)
        elif field.reference is not None:
            self.error("Only Reference fields may specify a reference target", field)
        if kind == self.Type.ENUM:
            if field.enum_type not in enums:
                self.error(f"Unknown enum '{field.enum_type}'", field)
            # Derive this rather than trusting values supplied by a client.
            field.enum_values = [member.value for member in enums[field.enum_type].members]
        elif field.enum_type is not None or field.enum_values is not None:
            self.error("Only enum fields may specify enum options", field)
        string_options = (field.min_length, field.max_length, field.pattern)
        if kind not in (self.Type.STRING, self.Type.TEXT) and any(
                x is not None for x in string_options
        ):
            self.error("String constraints require String or Text", field)
        if field.min_length is not None and field.min_length < 0:
            self.error("min_length must be non-negative", field)
        if field.max_length is not None and field.max_length <= 0:
            self.error("max_length must be positive", field)
        if (
                field.min_length is not None
                and field.max_length is not None
                and field.min_length > field.max_length
        ):
            self.error("min_length cannot exceed max_length", field)
        if field.pattern is not None:
            try:
                re.compile(field.pattern)
            except re.error as error:
                self.error(f"Invalid pattern: {error}", field)
        numeric = {self.Type.INTEGER, self.Type.BIG_INTEGER, self.Type.FLOAT, self.Type.DECIMAL}
        bounds = (field.gt, field.ge, field.lt, field.le)
        if kind not in numeric and any(x is not None for x in bounds):
            self.error("Numeric constraints require a numeric type", field)
        if any(
                type(x) not in (int, float) or not math.isfinite(x) for x in bounds if x is not None
        ):
            self.error("Numeric bounds must be finite numbers", field)
        if field.gt is not None and field.ge is not None:
            self.error("gt and ge cannot be used together", field)
        if field.lt is not None and field.le is not None:
            self.error("lt and le cannot be used together", field)
        lower = field.gt if field.gt is not None else field.ge
        upper = field.lt if field.lt is not None else field.le
        if lower is not None and upper is not None:
            if lower > upper or (lower == upper and (field.gt is not None or field.lt is not None)):
                self.error("Numeric bounds describe an empty range", field)
        if kind != self.Type.DECIMAL and (field.precision is not None or field.scale is not None):
            self.error("precision/scale require Decimal", field)
        if field.precision is not None and field.precision <= 0:
            self.error("precision must be positive", field)
        if field.scale is not None and field.scale < 0:
            self.error("scale must be non-negative", field)
        if (
                field.precision is not None
                and field.scale is not None
                and field.scale > field.precision
        ):
            self.error("scale cannot exceed precision", field)
        if kind == self.Type.SOURCE and (field.primary_key or field.default is not None):
            self.error("Source cannot have a primary key or static default", field)
        # A missing default differs from an explicitly declared null default.
        if field.has_default or field.default is not None:
            if kind == self.Type.REFERENCE and field.default is not None:
                self.error("Reference defaults must be null; use a seed reference instead", field)
            from business_layer.services.validation import validate_value

            try:
                validate_value(field.default, field.model_dump())
            except (ValueError, TypeError, OverflowError) as error:
                self.error(f"Invalid default: {error}", field)


# Resolve nested forward references once the enclosing namespace exists.
for _model in (Sema.EnumDefinition, Sema.Field, Sema.Entity, Sema.Schema):
    _model.model_rebuild()


def compile_source(code: str, **options):
    from business_layer.services.schema_parser import compile_source as compile_program

    return compile_program(code, **options)


def execute(code: str, **options):
    """Interpret declarations locally; persistence is an explicit separate operation."""
    return compile_source(code, **options)
