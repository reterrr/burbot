"""Compare field contracts across complete schema revisions."""

from typing import Any

from business_layer.services.schema_language import Sema
from business_layer.services.value_history import equal_json


def field_definition(field: Sema.Field) -> dict[str, Any]:
    """Serialize a field's semantics without source coordinates or enum ordering."""
    definition = field.model_dump(mode="json", exclude={"location": True, "item": {"location"}})
    for value_type in (definition, definition.get("item")):
        if value_type is not None and value_type.get("enum_values") is not None:
            value_type["enum_values"] = sorted(value_type["enum_values"], key=str)
    return definition


def structural_field_definition(
    field: Sema.Field, *, schema: Sema.Schema | None = None
) -> dict[str, Any]:
    """Keep all contract attributes except the explicitly editable metadata."""
    definition = field_definition(field)
    for key in ("name", "label", "description"):
        definition.pop(key, None)
    if schema is None:
        return definition

    for value_type in (definition, definition.get("item")):
        if value_type is None:
            continue
        if value_type.get("reference") is not None:
            target = next(
                entity for entity in schema.entities if entity.name == value_type["reference"]
            )
            value_type["reference"] = target.tablename
        if value_type.get("enum_type") is not None:
            enum = next(enum for enum in schema.enums if enum.name == value_type["enum_type"])
            value_type["enum_members"] = {member.name: member.value for member in enum.members}
    return definition


def is_structural_change(
    previous: Sema.Field,
    desired: Sema.Field,
    *,
    previous_schema: Sema.Schema | None = None,
    desired_schema: Sema.Schema | None = None,
) -> bool:
    return not equal_json(
        structural_field_definition(previous, schema=previous_schema),
        structural_field_definition(desired, schema=desired_schema),
    )
