"""The same List semantics apply to restricted source and JSON schemas."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from business_layer.services.entities import EntitiesService
from business_layer.services.schema_language import Sema
from business_layer.services.schema_parser import compile_source
from business_layer.services.validation import validate_value

PREFIX = """class State(Enum):
    OPEN = "open"
    CLOSED = "closed"
class Operator(Entity):
    name: String()
"""


def compile_list(declaration, options=""):
    return compile_source(
        PREFIX + f"class Project(Entity):\n    values: List({declaration}{options})\n"
    )


@pytest.mark.parametrize(
    "item,value",
    [
        ("String()", "hello"),
        ("Text()", "text"),
        ("Integer(ge=0, le=100)", 50),
        ("BigInteger()", 2**40),
        ("Float()", 1.5),
        ("Decimal(precision=14, scale=2)", "100.12"),
        ("Boolean()", False),
        ("Date()", "2026-11-18"),
        ("DateTime()", "2026-11-18T12:00:00Z"),
        ("UUID()", "11111111-1111-4111-8111-111111111111"),
        ("JSON()", {"nested": [True, None, 1]}),
        ("Reference('Operator')", 10),
        ("Source()", 20),
        ("State()", "open"),
    ],
)
def test_all_list_types_and_json_contract(item, value):
    program = compile_list(item)
    schema = Sema.Schema.model_validate_json(program.schema.model_dump_json())
    Sema().validate(schema)
    field = schema.entities[-1].fields[0]
    assert field.type == Sema.Type.LIST
    assert field.item.nullable is False
    validate_value([value, value], field.model_dump())
    with pytest.raises(ValueError, match="Null collection items"):
        validate_value([None], field.model_dump())


@pytest.mark.parametrize(
    "expression,message",
    [
        ("List()", "exactly one"),
        ("List(String(), Integer())", "exactly one"),
        ("List(Missing())", "Unknown type"),
        ("List(Reference('Missing'))", "Unknown referenced"),
        ("List(String(), min_items=2, max_items=1)", "min_items"),
        ("List(String(), unique=True)", "unique_items"),
        ("List(String(nullable=True))", "Null collection items"),
        ("List(String(default='x'))", "Item types"),
        ("List(String(), mystery=True)", "Unknown or repeated"),
        ("List(String(), min_items=True)", "valid integer"),
        ("List(String(), max_items=-1)", "greater than or equal"),
        ("List(String(ge=0))", "Numeric constraints"),
        ("String(min_items=1)", "Collection options"),
    ],
)
def test_invalid_definitions(expression, message):
    with pytest.raises((Sema.SemaException, ValidationError), match=message):
        compile_source(f"class Project(Entity):\n    field: {expression}\n")


def test_nested_dsl_and_json_share_specific_error():
    with pytest.raises(Sema.SemaException) as raised:
        compile_list("List(String())")
    assert raised.value.code == "UNSUPPORTED_NESTED_COLLECTION"
    raw = compile_list("String()").schema.model_dump()
    field = raw["entities"][-1]["fields"][0]
    field["item"] = {"type": "list", "item": {"type": "string"}}
    with pytest.raises(Sema.SemaException) as raised:
        Sema().validate(Sema.Schema.model_validate(raw))
    assert raised.value.code == "UNSUPPORTED_NESTED_COLLECTION"


def test_minimal_json_item_definition_and_enum_validation():
    raw = compile_list("State()").schema.model_dump()
    field = raw["entities"][-1]["fields"][0]
    field["item"] = {"type": "enum", "enum_type": "State", "enum_values": ["forged"]}
    schema = Sema().validate(Sema.Schema.model_validate(raw))
    assert schema.entities[-1].fields[0].item.enum_values == ["open", "closed"]
    field["item"]["enum_type"] = "Missing"
    with pytest.raises(Sema.SemaException, match="Unknown enum"):
        Sema().validate(Sema.Schema.model_validate(raw))


def test_item_constraints_and_logical_uniqueness():
    definition = (
        compile_list(
            "Decimal(precision=4, scale=2)", ", min_items=1, max_items=2, unique_items=True"
        )
        .schema.entities[-1]
        .fields[0]
        .model_dump()
    )
    validate_value(["1.00", "2.00"], definition)
    for value, message in [
        ([], "min_items"),
        ([1, 2, 3], "max_items"),
        (["1.00", 1], "unique_items"),
        (["100.00"], "precision|integer digits"),
    ]:
        with pytest.raises(ValueError, match=message):
            validate_value(value, definition)
    validate_value(None, definition)
    validate_value([True, 1], {"type": "list", "unique_items": True, "item": {"type": "json"}})
    with pytest.raises(ValueError, match="unique_items"):
        validate_value(
            [{"a": 1, "b": 2}, {"b": 2, "a": 1}],
            {"type": "list", "unique_items": True, "item": {"type": "json"}},
        )


def test_schema_hash_and_diff_include_item_rules_but_not_locations():
    first = compile_list("Integer()")
    moved = compile_source(
        "\n\n" + PREFIX + "class Project(Entity):\n    values: List(\n        Integer()\n    )\n"
    )
    assert EntitiesService(None)._schema_hash(first.schema) == EntitiesService(None)._schema_hash(
        moved.schema
    )
    changed = deepcopy(first.schema)
    changed.entities[-1].fields[0].max_items = 10
    assert EntitiesService(None)._schema_hash(first.schema) != EntitiesService(None)._schema_hash(
        changed
    )
    assert EntitiesService(None)._find_changes(current=first.schema, desired=changed)
    changed.entities[-1].fields[0].item.type = Sema.Type.STRING
    assert EntitiesService(None)._find_changes(current=first.schema, desired=changed)


def test_seed_references_inside_lists_and_empty_defaults():
    source = (
        PREFIX
        + """class Project(Entity):
    operators: List(Reference("Operator"), unique_items=True)
    tags: List(String(), nullable=False, default=[])
project = Project(operators=[second, first.id])
first = Operator(name="First")
second = Operator(name="Second")
"""
    )
    plan = compile_source(source)
    assert plan.seed_order.index("project") > plan.seed_order.index("first")
    assert plan.objects[0].values["tags"] == []
    with pytest.raises(Sema.SemaException, match="unique_items"):
        compile_source(source.replace("[second, first.id]", "[first, first]"))
    with pytest.raises(Sema.SemaException, match="must reference"):
        compile_source(source.replace("[second, first.id]", "[missing]"))


def test_unique_items_normalizes_numeric_zero_and_json_numbers_without_boolean_coercion():
    for definition, duplicates in [
        ({"type": "list", "unique_items": True, "item": {"type": "decimal"}}, ["-0.00", 0]),
        ({"type": "list", "unique_items": True, "item": {"type": "json"}}, [1, 1.0]),
        (
            {"type": "list", "unique_items": True, "item": {"type": "json"}},
            [{"a": [1]}, {"a": [1.0]}],
        ),
    ]:
        with pytest.raises(ValueError, match="unique_items"):
            validate_value(duplicates, definition)
    validate_value([True, 1], {"type": "list", "unique_items": True, "item": {"type": "json"}})
