"""Structural comparison for validated field declarations."""

from business_layer.services.schema_evolution import (
    is_structural_change,
    structural_field_definition,
)
from business_layer.services.schema_language import Sema
from business_layer.services.schema_parser import compile_source


def first_field(declaration):
    schema = compile_source(f"class Project(Entity):\n    {declaration}\n").schema
    return schema.entities[0].fields[0]


def test_structural_comparison_ignores_only_metadata_and_locations():
    old = first_field("score: List(Integer(ge=0))")
    new = first_field(
        'rating: List(Integer(ge=0), persistent_key="score", label="Rating", description="Units")'
    )
    assert not is_structural_change(old, new)
    item = structural_field_definition(new)["item"]
    assert item["ge"] == 0 and "location" not in item
    assert is_structural_change(old, new.model_copy(update={"persistent_key": "rating"}))
    new.item.ge = 1
    assert is_structural_change(old, new)


def test_unknown_attributes_and_type_sensitive_defaults_are_structural():
    class ExtendedField(Sema.Field):
        storage_format: str = "original"

    field = ExtendedField.model_validate(first_field("data: JSON(default=True)").model_dump())
    assert is_structural_change(field, field.model_copy(update={"storage_format": "changed"}))
    assert is_structural_change(field, field.model_copy(update={"default": 1}))


def test_reference_comparison_uses_target_identity_at_each_revision():
    old = compile_source(
        "class Operator(Entity):\n    pass\nclass Project(Entity):\n    refs: List(Operator)\n"
    ).schema
    target, project = old.entities
    desired = compile_source(
        f'class Vendor(Entity, tablename="{target.tablename}"):\n    pass\n'
        "class Project(Entity):\n    refs: List(Vendor)\n"
    ).schema
    new = desired.entities[1].fields[0]
    assert not is_structural_change(
        project.fields[0], new, previous_schema=old, desired_schema=desired
    )
    desired.entities[0].tablename = project.tablename
    assert is_structural_change(project.fields[0], new, previous_schema=old, desired_schema=desired)
